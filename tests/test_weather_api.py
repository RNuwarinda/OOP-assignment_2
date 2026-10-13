"""Offline checks for the weather response parsers and HTTP retry policy."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import requests

from src.weather_api import (
    WeatherAPIError,
    get_forecast,
    parse_forecast,
    parse_geocoding,
    parse_metno,
    request_json,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    with (FIXTURES / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


class WeatherParsingTests(unittest.TestCase):
    def test_geocoding_candidates_are_parsed(self):
        candidates = parse_geocoding(load_fixture("geocoding.json"))
        self.assertEqual(candidates[0]["name"], "Dresden")

    def test_missing_geocoding_results_are_empty(self):
        self.assertEqual(parse_geocoding(load_fixture("geocoding_empty.json")), [])

    def test_forecast_columns_and_weather_codes_are_readable(self):
        frame = parse_forecast(load_fixture("forecast.json"))
        self.assertEqual(frame.loc[0, "Conditions"], "Mainly clear")
        self.assertEqual(frame.loc[1, "Conditions"], "Slight rain")
        self.assertEqual(frame.loc[2, "Max wind (km/h)"], 22.1)

    def test_forecast_rejects_misaligned_daily_arrays(self):
        with self.assertRaises(WeatherAPIError):
            parse_forecast(load_fixture("forecast_invalid_lengths.json"))

    def test_metno_compact_forecast_is_normalized(self):
        rows = parse_metno(load_fixture("metno.json"))
        self.assertEqual(rows[0]["Symbol"], "partlycloudy_day")
        self.assertEqual(rows[0]["Temperature (°C)"], 11.3)

    def test_invalid_latitude_fails_before_network_access(self):
        with self.assertRaisesRegex(ValueError, "latitude"):
            get_forecast(91, 13.7, 3)

    def test_connection_failure_raises_custom_error_after_retry_cap(self):
        class OfflineSession:
            calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                raise requests.ConnectionError("simulated offline")

        session = OfflineSession()
        with self.assertRaisesRegex(WeatherAPIError, "3 attempts"):
            request_json("https://example.invalid", {}, session=session, sleep_fn=lambda _: None)
        self.assertEqual(session.calls, 3)

    def test_server_error_is_retried(self):
        class ServerErrorSession:
            calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                response = SimpleNamespace(status_code=503)
                error = requests.HTTPError("service unavailable", response=response)
                raise error

        session = ServerErrorSession()
        with self.assertRaisesRegex(WeatherAPIError, "HTTP 503"):
            request_json("https://example.invalid", {}, session=session, sleep_fn=lambda _: None)
        self.assertEqual(session.calls, 3)


if __name__ == "__main__":
    unittest.main()