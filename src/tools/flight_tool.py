"""
Flight Tool — CrewAI tool for the Flight Agent.

Sources:
  - AviationStack API  : flight status, route, delay info (primary)
  - OpenSky Network    : real-time position fallback (no auth required)
"""
from __future__ import annotations

import requests
from crewai.tools import BaseTool
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
_settings = get_settings()

AVIATIONSTACK_URL = "http://api.aviationstack.com/v1"
OPENSKY_URL = "https://opensky-network.org/api"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _aviationstack_flight(flight_iata: str) -> dict | None:
    resp = requests.get(
        f"{AVIATIONSTACK_URL}/flights",
        params={
            "access_key": _settings.aviationstack_api_key,
            "flight_iata": flight_iata,
            "limit": 1,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    flights = data.get("data", [])
    return flights[0] if flights else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _aviationstack_airport(iata_code: str) -> dict | None:
    resp = requests.get(
        f"{AVIATIONSTACK_URL}/airports",
        params={
            "access_key": _settings.aviationstack_api_key,
            "iata_code": iata_code,
            "limit": 1,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    airports = data.get("data", [])
    return airports[0] if airports else None


def _format_flight(flight: dict) -> str:
    """Format an AviationStack flight record into readable text."""
    dep = flight.get("departure", {})
    arr = flight.get("arrival", {})
    fl = flight.get("flight", {})
    aircraft = flight.get("aircraft") or {}
    airline = flight.get("airline", {})

    status = flight.get("flight_status", "unknown").upper()
    delay_dep = dep.get("delay") or 0
    delay_arr = arr.get("delay") or 0

    lines = [
        "## FLIGHT STATUS REPORT",
        f"Flight        : {fl.get('iata', 'N/A')} ({fl.get('icao', 'N/A')})",
        f"Airline       : {airline.get('name', 'N/A')}",
        f"Status        : {status}",
        f"Aircraft      : {aircraft.get('iata', 'N/A')} | Registration: {aircraft.get('registration', 'N/A')}",
        "",
        "DEPARTURE",
        f"  Airport     : {dep.get('airport', 'N/A')} ({dep.get('iata', 'N/A')})",
        f"  Scheduled   : {dep.get('scheduled', 'N/A')}",
        f"  Estimated   : {dep.get('estimated', 'N/A')}",
        f"  Actual      : {dep.get('actual', 'N/A')}",
        f"  Delay       : {delay_dep} minutes",
        f"  Terminal    : {dep.get('terminal', 'N/A')} | Gate: {dep.get('gate', 'N/A')}",
        "",
        "ARRIVAL",
        f"  Airport     : {arr.get('airport', 'N/A')} ({arr.get('iata', 'N/A')})",
        f"  Scheduled   : {arr.get('scheduled', 'N/A')}",
        f"  Estimated   : {arr.get('estimated', 'N/A')}",
        f"  Actual      : {arr.get('actual', 'N/A')}",
        f"  Delay       : {delay_arr} minutes",
        f"  Terminal    : {arr.get('terminal', 'N/A')} | Baggage: {arr.get('baggage', 'N/A')}",
    ]

    if delay_dep >= 180:
        lines.append("\n⚠ Delay exceeds 3 hours — EU261/2004 compensation may apply.")
    elif delay_dep >= 120:
        lines.append("\n⚠ Delay exceeds 2 hours — meals and refreshments required.")

    return "\n".join(lines)


def get_flight_status(flight_iata: str) -> str:
    """
    Fetch real-time status for a given flight IATA code.
    Returns a formatted string for agent consumption.
    """
    logger.info("flight_status_fetch", flight=flight_iata)
    try:
        flight = _aviationstack_flight(flight_iata.upper())
        if flight:
            result = _format_flight(flight)
            logger.info("flight_status_success", flight=flight_iata)
            return result
        # Fallback message if not found
        return (
            f"Flight {flight_iata} not found in AviationStack. "
            "This may be a future or historical flight. "
            "Using available information from the user request to proceed."
        )
    except Exception as exc:
        logger.error("flight_status_error", flight=flight_iata, error=str(exc))
        return (
            f"Could not fetch live status for {flight_iata}: {exc}. "
            "Proceeding with information from user request."
        )


def get_alternative_flights(origin: str, destination: str) -> str:
    """
    Search for alternative flights between origin and destination.
    Returns top options as formatted text.
    """
    logger.info("alt_flights_search", origin=origin, destination=destination)
    try:
        resp = requests.get(
            f"{AVIATIONSTACK_URL}/flights",
            params={
                "access_key": _settings.aviationstack_api_key,
                "dep_iata": origin.upper(),
                "arr_iata": destination.upper(),
                "flight_status": "scheduled",
                "limit": 5,
            },
            timeout=15,
        )
        resp.raise_for_status()
        flights = resp.json().get("data", [])

        if not flights:
            return f"No scheduled alternative flights found from {origin} to {destination}."

        lines = [f"## ALTERNATIVE FLIGHTS: {origin} → {destination}"]
        for i, f in enumerate(flights, 1):
            fl = f.get("flight", {})
            dep = f.get("departure", {})
            arr = f.get("arrival", {})
            lines.append(
                f"{i}. {fl.get('iata','N/A')} | "
                f"Dep: {dep.get('scheduled','N/A')} | "
                f"Arr: {arr.get('scheduled','N/A')} | "
                f"Status: {f.get('flight_status','N/A').upper()}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.error("alt_flights_error", error=str(exc))
        return f"Alternative flight search failed: {exc}"


class FlightTool(BaseTool):
    name: str = "Flight Status and Alternatives Tool"
    description: str = (
        "Retrieve real-time flight status, delay information, aircraft registration, "
        "departure/arrival times, and alternative flight options. "
        "Supported input formats:\n"
        "  1. Single flight status  : 'STATUS:AI302'\n"
        "  2. Alternative flights   : 'ALTERNATIVES:DEL,LHR'\n"
        "Use STATUS for delay/status lookup and ALTERNATIVES to find rebooking options."
    )

    def _run(self, query: str) -> str:
        logger.info("flight_tool_called", input=query)
        q = query.strip()
        if q.upper().startswith("STATUS:"):
            flight_iata = q.split(":", 1)[1].strip()
            return get_flight_status(flight_iata)
        elif q.upper().startswith("ALTERNATIVES:"):
            pair = q.split(":", 1)[1].strip()
            parts = [p.strip().upper() for p in pair.split(",")]
            if len(parts) != 2:
                return "Error: ALTERNATIVES expects 'ORIGIN,DESTINATION' e.g. 'DEL,LHR'."
            return get_alternative_flights(parts[0], parts[1])
        else:
            # Try treating as plain flight code
            return get_flight_status(q.upper())


flight_tool = FlightTool()
