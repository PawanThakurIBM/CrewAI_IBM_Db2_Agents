"""
Weather Tool — CrewAI tool for the Weather Agent.

Sources:
  - OpenWeatherMap API  : current conditions + 5-day forecast
  - aviationweather.gov : METAR + TAF (free, no auth)
"""
from __future__ import annotations

import json
from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import Field
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
_settings = get_settings()

# ── IATA→ICAO mapping for common airports on Delhi–London route ──────────────
IATA_TO_ICAO: dict[str, str] = {
    "DEL": "VIDP",  # Indira Gandhi International
    "LHR": "EGLL",  # London Heathrow
    "LGW": "EGKK",  # London Gatwick
    "BOM": "VABB",  # Mumbai
    "DXB": "OMDB",  # Dubai
    "DOH": "OTHH",  # Doha
    "FRA": "EDDF",  # Frankfurt
    "CDG": "LFPG",  # Paris Charles de Gaulle
    "AMS": "EHAM",  # Amsterdam
    "IST": "LTFM",  # Istanbul
}


def _icao(iata: str) -> str:
    """Convert IATA to ICAO, fallback to uppercase IATA."""
    return IATA_TO_ICAO.get(iata.upper(), iata.upper())


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _owm_current(city: str) -> dict:
    url = "https://api.openweathermap.org/data/2.5/weather"
    resp = requests.get(
        url,
        params={"q": city, "appid": _settings.openweather_api_key, "units": "metric"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _owm_forecast(city: str) -> dict:
    url = "https://api.openweathermap.org/data/2.5/forecast"
    resp = requests.get(
        url,
        params={
            "q": city,
            "appid": _settings.openweather_api_key,
            "units": "metric",
            "cnt": 8,  # 24 hours (3h steps × 8)
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _avwx_metar(icao: str) -> list[dict]:
    url = "https://aviationweather.gov/api/data/metar"
    resp = requests.get(
        url, params={"ids": icao, "format": "json"}, timeout=10
    )
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _avwx_taf(icao: str) -> list[dict]:
    url = "https://aviationweather.gov/api/data/taf"
    resp = requests.get(
        url, params={"ids": icao, "format": "json"}, timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def _classify_severity(wind_speed_ms: float, visibility_m: float, weather_ids: list[int]) -> str:
    """
    Simple severity classifier based on OWM weather codes, wind, and visibility.

    Returns one of: Low | Medium | High | Severe
    """
    # Thunderstorm or extreme (2xx, 9xx)
    if any(200 <= wid < 300 or wid >= 900 for wid in weather_ids):
        return "Severe"
    # Heavy rain / snow / ice (5xx heavy, 6xx heavy)
    if any(502 <= wid <= 504 or 522 <= wid <= 531 or 602 <= wid <= 621 for wid in weather_ids):
        return "High"
    # Low visibility or strong winds
    if visibility_m < 1500 or wind_speed_ms > 15:
        return "High"
    if visibility_m < 5000 or wind_speed_ms > 10:
        return "Medium"
    return "Low"


def get_weather_report(departure_iata: str, arrival_iata: str) -> str:
    """
    Fetch full weather report for departure and arrival airports.
    Returns a formatted string suitable for agent consumption.
    """
    sections: list[str] = []

    for label, iata in [("DEPARTURE", departure_iata), ("ARRIVAL", arrival_iata)]:
        icao = _icao(iata)
        city_name = iata  # fallback display name
        lines: list[str] = [f"## {label} AIRPORT: {iata} (ICAO: {icao})"]

        # ── OpenWeatherMap current ───────────────────────────────────────────
        try:
            owm = _owm_current(iata)
            city_name = owm.get("name", iata)
            weather_desc = owm["weather"][0]["description"].title()
            temp = owm["main"]["temp"]
            wind_speed = owm["wind"]["speed"]
            visibility = owm.get("visibility", 10000)
            weather_ids = [w["id"] for w in owm["weather"]]
            severity = _classify_severity(wind_speed, visibility, weather_ids)

            lines += [
                f"City          : {city_name}",
                f"Conditions    : {weather_desc}",
                f"Temperature   : {temp}°C",
                f"Wind Speed    : {wind_speed} m/s",
                f"Visibility    : {visibility} m",
                f"Severity      : {severity}",
            ]
            logger.info("owm_fetched", airport=iata, severity=severity)
        except Exception as exc:
            lines.append(f"OpenWeatherMap fetch failed: {exc}")
            logger.warning("owm_fetch_failed", airport=iata, error=str(exc))

        # ── OWM Forecast (next 24h summary) ──────────────────────────────────
        try:
            fc = _owm_forecast(iata)
            conditions_24h = list({
                entry["weather"][0]["description"].title()
                for entry in fc.get("list", [])
            })
            lines.append(f"24h Forecast  : {', '.join(conditions_24h[:4])}")
        except Exception as exc:
            lines.append(f"Forecast fetch failed: {exc}")

        # ── METAR ─────────────────────────────────────────────────────────────
        try:
            metars = _avwx_metar(icao)
            if metars:
                raw = metars[0].get("rawOb", metars[0].get("rawObs", "N/A"))
                lines.append(f"METAR         : {raw}")
        except Exception as exc:
            lines.append(f"METAR fetch failed: {exc}")

        # ── TAF ───────────────────────────────────────────────────────────────
        try:
            tafs = _avwx_taf(icao)
            if tafs:
                raw_taf = tafs[0].get("rawTAF", tafs[0].get("rawTaf", "N/A"))
                lines.append(f"TAF           : {raw_taf}")
        except Exception as exc:
            lines.append(f"TAF fetch failed: {exc}")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


class WeatherTool(BaseTool):
    name: str = "Weather Information Tool"
    description: str = (
        "Retrieve real-time weather conditions, METAR, TAF, and 24-hour forecasts "
        "for departure and arrival airports. "
        "Input format: 'DEPARTURE_IATA,ARRIVAL_IATA' e.g. 'DEL,LHR'. "
        "Returns current conditions, wind, visibility, severity level (Low/Medium/High/Severe), "
        "METAR, TAF, and forecast summary for both airports."
    )

    def _run(self, airport_pair: str) -> str:
        logger.info("weather_tool_called", input=airport_pair)
        try:
            parts = [p.strip().upper() for p in airport_pair.split(",")]
            if len(parts) != 2:
                return "Error: provide exactly two IATA codes separated by a comma, e.g. 'DEL,LHR'."
            result = get_weather_report(parts[0], parts[1])
            logger.info("weather_tool_success", departure=parts[0], arrival=parts[1])
            return result
        except Exception as exc:
            logger.error("weather_tool_error", error=str(exc))
            return f"Weather tool error: {exc}"


weather_tool = WeatherTool()
