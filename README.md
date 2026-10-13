# Mini-Project 1: Weather Forecast

A Python notebook that searches for a place, fetches a local-time Open-Meteo daily forecast, and displays a table, summary, and temperature/precipitation chart. HTTP calls, validation, retry policy, and response parsing are reusable functions in `src/weather_api.py`.

## Setup

Python 3.10 or newer is recommended.

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

In VS Code, open `project1_weather.ipynb`, choose the workspace `venv` Python kernel, and use **Restart & Run All**. The notebook has one configuration cell for location, forecast days, candidate selection, and contact email. Before enabling the MET Norway request, replace `YOUR_UNIVERSITY_EMAIL` with your own university email or set the `UNIVERSITY_EMAIL` environment variable. Do not commit personal contact details if the repository is public; configure the environment variable locally instead.

The default city is Dresden. If a place has multiple matches, all candidates are listed and `CANDIDATE_INDEX` in the configuration cell chooses the location. If the live geocoding or forecast request fails, the notebook clearly switches to the saved fixture and completes without pretending that sample values are current.

## Tests

Tests use saved JSON and do not contact the APIs:

```powershell
python -m unittest discover -s tests -v
```

Eight tests check geocoding results, empty results, forecast parsing and WMO descriptions, invalid response shape, MET Norway parsing, coordinate validation, offline failure, and retry behavior. The notebook also runs eight fixture-backed assertions. The project does not use random sampling, so a random seed is not applicable.

## Findings

In the verified live run on 10 October 2026, the Open-Meteo geocoding request returned HTTP 200 with an `application/json` content type in about 3.681 seconds. The selected result was Dresden, Saxony, Germany; the seven-day forecast had a maximum daily high of 19.7 °C on 16 October and maximum daily precipitation of 4.4 mm on 10 October. These are observations from that run only; forecasts change over time. The MET Norway call was not made because the contact email remains a placeholder.

The offline sample checks decode WMO code 1 as “Mainly clear” and code 61 as “Slight rain,” and preserve daily units in the output columns. Requests have bounded exponential retries for network errors and server errors, while invalid coordinates fail before a network call. Live API availability and response times depend on the providers and network.

## Sources and terms

- Forecast and geocoding: [Open-Meteo documentation](https://open-meteo.com/en/docs) and [geocoding documentation](https://open-meteo.com/en/docs/geocoding-api).
- Open-Meteo API data use [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) with attribution. Its free API is for non-commercial use and subject to published call limits; review [current terms](https://open-meteo.com/en/terms) before reuse.
- Second source: [MET Norway Locationforecast 2.0](https://api.met.no/weatherapi/locationforecast/2.0/documentation). Its policy requires a descriptive User-Agent with contact details, low traffic, and CC BY 4.0 attribution. Review the [current Terms of Service](https://api.met.no/doc/TermsOfService) before deployment.
- Location results are based on GeoNames as described by the geocoding documentation.

Forecast data are model outputs and are not guaranteed to be accurate or continuously available. This coursework notebook is not suitable as a safety-critical source.

## Repository submission

The configured GitHub remote is `https://github.com/RNuwarinda/OOP-assignment_2`. Push the repository there, confirm the notebook and fixtures are present, and submit that single repository URL on Moodle. This workspace does not push changes automatically.