"""
Airport Tool — CrewAI tool for the Runway Agent.

Sources:
  - aviationweather.gov : NOTAMs (free, no auth)
  - AviationStack       : Airport metadata
"""
from __future__ import annotations

import requests
from crewai.tools import BaseTool
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
_settings = get_settings()

IATA_TO_ICAO: dict[str, str] = {
    "DEL": "VIDP",
    "LHR": "EGLL",
    "LGW": "EGKK",
    "BOM": "VABB",
    "DXB": "OMDB",
    "DOH": "OTHH",
    "FRA": "EDDF",
    "CDG": "LFPG",
    "AMS": "EHAM",
    "IST": "LTFM",
}


def _icao(iata: str) -> str:
    return IATA_TO_ICAO.get(iata.upper(), iata.upper())


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _fetch_notams(icao: str) -> list[dict]:
    resp = requests.get(
        "https://aviationweather.gov/api/data/notam",
        params={"icaos": icao, "format": "json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json() if resp.text.strip().startswith("[") else []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _fetch_airport_meta(iata: str) -> dict | None:
    resp = requests.get(
        "http://api.aviationstack.com/v1/airports",
        params={
            "access_key": _settings.aviationstack_api_key,
            "iata_code": iata.upper(),
            "limit": 1,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0] if data else None


def _parse_notam_severity(notams: list[dict]) -> str:
    """Classify overall NOTAM severity for runway/airport ops."""
    if not notams:
        return "No active NOTAMs"
    runway_closed = any(
        "RWY" in str(n.get("text", "")).upper() and "CLSD" in str(n.get("text", "")).upper()
        for n in notams
    )
    if runway_closed:
        return "RUNWAY CLOSURE NOTAM ACTIVE"
    return f"{len(notams)} active NOTAM(s)"


def get_airport_status(iata: str) -> str:
    """Return full airport operational status including NOTAMs and metadata."""
    icao = _icao(iata)
    lines = [f"## AIRPORT STATUS: {iata} (ICAO: {icao})"]

    # ── AviationStack metadata ───────────────────────────────────────────────
    try:
        meta = _fetch_airport_meta(iata)
        if meta:
            lines += [
                f"Name          : {meta.get('airport_name', 'N/A')}",
                f"Country       : {meta.get('country_name', 'N/A')}",
                f"Timezone      : {meta.get('timezone', 'N/A')}",
                f"Latitude      : {meta.get('latitude', 'N/A')}",
                f"Longitude     : {meta.get('longitude', 'N/A')}",
            ]
    except Exception as exc:
        lines.append(f"Airport metadata fetch failed: {exc}")
        logger.warning("airport_meta_failed", airport=iata, error=str(exc))

    # ── NOTAMs ───────────────────────────────────────────────────────────────
    try:
        notams = _fetch_notams(icao)
        notam_summary = _parse_notam_severity(notams)
        lines.append(f"NOTAM Status  : {notam_summary}")

        if notams:
            lines.append("\nActive NOTAMs (top 5):")
            for n in notams[:5]:
                text = n.get("traditionalMessage") or n.get("text", "N/A")
                lines.append(f"  • {str(text)[:200]}")
        else:
            lines.append("NOTAMs        : None active")

        logger.info("notams_fetched", airport=icao, count=len(notams))
    except Exception as exc:
        lines.append(f"NOTAM fetch failed: {exc}")
        logger.warning("notam_fetch_failed", airport=icao, error=str(exc))

    return "\n".join(lines)


class AirportTool(BaseTool):
    name: str = "Airport Operations and NOTAM Tool"
    description: str = (
        "Retrieve airport operational status, active NOTAMs (Notice to Air Missions), "
        "runway closure notices, and airport metadata for any IATA airport code. "
        "Input: a single IATA airport code, e.g. 'DEL' or 'LHR'. "
        "Returns NOTAM summary, any runway closure advisories, and airport metadata."
    )

    def _run(self, iata_code: str) -> str:
        logger.info("airport_tool_called", input=iata_code)
        iata = iata_code.strip().upper()
        if len(iata) != 3:
            return "Error: provide a valid 3-letter IATA airport code, e.g. 'DEL'."
        result = get_airport_status(iata)
        logger.info("airport_tool_success", airport=iata)
        return result


airport_tool = AirportTool()
