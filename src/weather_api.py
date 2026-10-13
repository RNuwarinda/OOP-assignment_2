"""HTTP clients and parsers for Open-Meteo and MET Norway weather APIs."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import pandas as pd
import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
METNO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
DEFAULT_TIMEOUT = 10.0
MAX_RETRIES = 2
BACKOFF_BASE_SECONDS = 0.5

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    97: "Heavy thunderstorm",
    99: "Thunderstorm with heavy hail",
}


class WeatherAPIError(RuntimeError):
    """Raised when an API request or response cannot be used."""


@dataclass(frozen=True)
class RequestResult:
    """JSON response data and basic HTTP diagnostics."""

    data: dict[str, Any]
    status_code: int
    content_type: str
    elapsed_seconds: float


def request_json(
    url: str,
    params: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    session: Any = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> RequestResult:
    """GET JSON with a timeout and capped exponential retries for transient errors."""
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")

    client = session or requests
    for attempt in range(max_retries + 1):
        try:
            response = client.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = error.response.status_code if error.response else None
            if status_code is not None and 500 <= status_code < 600 and attempt < max_retries:
                sleep_fn(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            raise WeatherAPIError(f"HTTP {status_code} from {url}") from error
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt < max_retries:
                sleep_fn(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            raise WeatherAPIError(f"Request to {url} failed after {attempt + 1} attempts: {error}") from error
        except requests.RequestException as error:
            raise WeatherAPIError(f"Request to {url} failed: {error}") from error

        try:
            data = response.json()
        except ValueError as error:
            raise WeatherAPIError(f"The response from {url} was not valid JSON") from error
        if not isinstance(data, dict):
            raise WeatherAPIError(f"The response from {url} was not a JSON object")
        elapsed = response.elapsed.total_seconds()
        return RequestResult(
            data=data,
            status_code=response.status_code,
            content_type=response.headers.get("Content-Type", ""),
            elapsed_seconds=elapsed,
        )

    raise WeatherAPIError(f"Request to {url} failed after {max_retries + 1} attempts")


def urllib_request_json(
    url: str,
    params: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> RequestResult:
    """GET JSON with urllib, including timeout, HTTP checks, and capped retries."""
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")

    query = urllib.parse.urlencode(params)
    request_url = f"{url}?{query}"
    request_headers = dict(headers or {})
    request_headers.setdefault("User-Agent", "WeatherForecastAssignment/1.0")

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(request_url, headers=request_headers)
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_data = response.read()
                status_code = response.status
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            if 500 <= error.code < 600 and attempt < max_retries:
                sleep_fn(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            raise WeatherAPIError(f"HTTP {error.code} from {url}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt < max_retries:
                sleep_fn(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            raise WeatherAPIError(f"Request to {url} failed after {attempt + 1} attempts: {error}") from error

        try:
            data = json.loads(raw_data)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise WeatherAPIError(f"The response from {url} was not valid JSON") from error
        if not isinstance(data, dict):
            raise WeatherAPIError(f"The response from {url} was not a JSON object")
        return RequestResult(
            data=data,
            status_code=status_code,
            content_type=content_type,
            elapsed_seconds=time.perf_counter() - started,
        )

    raise WeatherAPIError(f"Request to {url} failed after {max_retries + 1} attempts")


def parse_geocoding(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return valid location candidates; missing or empty results mean no match."""
    candidates = payload.get("results", [])
    if not isinstance(candidates, list):
        raise WeatherAPIError("Geocoding response 'results' must be a list")
    return [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict)
        and isinstance(candidate.get("latitude"), (int, float))
        and isinstance(candidate.get("longitude"), (int, float))
    ]


def geocode(
    name: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Search Open-Meteo's geocoder and return all valid candidate locations."""
    if not name.strip():
        return []
    result = request_json(
        GEOCODING_URL,
        {"name": name.strip(), "count": 10, "language": "en", "format": "json"},
        headers=headers,
        timeout=timeout,
    )
    return parse_geocoding(result.data)


def get_forecast(
    lat: float,
    lon: float,
    days: int,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch daily Open-Meteo forecast data for validated WGS84 coordinates."""
    if not -90 <= lat <= 90:
        raise ValueError("latitude must be between -90 and 90 degrees")
    if not -180 <= lon <= 180:
        raise ValueError("longitude must be between -180 and 180 degrees")
    if not 1 <= days <= 16:
        raise ValueError("days must be between 1 and 16")

    result = request_json(
        FORECAST_URL,
        {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                "wind_speed_10m_max,weather_code"
            ),
            "forecast_days": days,
            "timezone": "auto",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        },
        headers=headers,
        timeout=timeout,
    )
    return result.data


def parse_forecast(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Validate and normalize Open-Meteo daily JSON into a labeled DataFrame."""
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise WeatherAPIError("Forecast response has no daily data object")

    source_fields = {
        "time": "Date",
        "temperature_2m_min": "Min temp (°C)",
        "temperature_2m_max": "Max temp (°C)",
        "precipitation_sum": "Precipitation (mm)",
        "wind_speed_10m_max": "Max wind (km/h)",
        "weather_code": "Weather code",
    }
    missing = [field for field in source_fields if field not in daily]
    if missing:
        raise WeatherAPIError(f"Forecast response is missing daily fields: {', '.join(missing)}")

    lengths = {len(daily[field]) for field in source_fields}
    if len(lengths) != 1:
        raise WeatherAPIError("Forecast daily fields do not have matching lengths")

    frame = pd.DataFrame({label: daily[field] for field, label in source_fields.items()})
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["Conditions"] = frame["Weather code"].map(
        lambda code: WEATHER_CODES.get(int(code), f"Unknown (WMO {code})")
        if pd.notna(code)
        else "Unavailable"
    )
    return frame.drop(columns="Weather code")


def fetch_metno(
    lat: float,
    lon: float,
    *,
    user_agent: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch a compact MET Norway forecast using the required identifying UA."""
    if not -90 <= lat <= 90:
        raise ValueError("latitude must be between -90 and 90 degrees")
    if not -180 <= lon <= 180:
        raise ValueError("longitude must be between -180 and 180 degrees")
    if not user_agent.strip() or "YOUR_UNIVERSITY_EMAIL" in user_agent:
        raise ValueError("Set your real university email in the MET Norway User-Agent")

    result = request_json(
        METNO_URL,
        {"lat": round(lat, 4), "lon": round(lon, 4)},
        headers={"User-Agent": user_agent},
        timeout=timeout,
    )
    return result.data


def parse_metno(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract time, temperature, precipitation, wind, and symbol from compact JSON."""
    try:
        series = payload["properties"]["timeseries"]
    except (KeyError, TypeError) as error:
        raise WeatherAPIError("MET Norway response has no properties.timeseries") from error
    if not isinstance(series, list):
        raise WeatherAPIError("MET Norway timeseries must be a list")

    parsed = []
    for entry in series:
        try:
            details = entry["data"]["instant"]["details"]
            next_1_hours = entry["data"].get("next_1_hours", {}).get("details", {})
            symbol = entry["data"].get("next_1_hours", {}).get("summary", {}).get("symbol_code")
            parsed.append(
                {
                    "Time": entry["time"],
                    "Temperature (°C)": details.get("air_temperature"),
                    "Precipitation (mm)": next_1_hours.get("precipitation_amount"),
                    "Wind (m/s)": details.get("wind_speed"),
                    "Symbol": symbol or "Not provided",
                }
            )
        except (KeyError, TypeError) as error:
            raise WeatherAPIError("MET Norway timeseries contains an invalid entry") from error
    return parsed