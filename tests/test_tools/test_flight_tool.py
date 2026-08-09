"""
Exhaustive tests for FlightTool.

Covers: STATUS: / ALTERNATIVES: routing, _format_flight output,
delay threshold warnings, error handling, fallback for missing flight.
All HTTP calls are mocked.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.tools.flight_tool import FlightTool, _format_flight, flight_tool


# ── _format_flight ────────────────────────────────────────────────────────────

class TestFormatFlight:
    def _sample_flight(self, delay_dep=0, status="active"):
        return {
            "flight_status": status,
            "flight": {"iata": "AI302", "icao": "AIC302"},
            "airline": {"name": "Air India"},
            "aircraft": {"iata": "B788", "registration": "VT-ANQ"},
            "departure": {
                "airport": "Indira Gandhi", "iata": "DEL",
                "scheduled": "2024-01-15T12:30:00",
                "estimated": "2024-01-15T14:00:00",
                "actual": None, "delay": delay_dep,
                "terminal": "3", "gate": "28",
            },
            "arrival": {
                "airport": "Heathrow", "iata": "LHR",
                "scheduled": "2024-01-15T17:30:00",
                "estimated": None, "actual": None, "delay": 0,
                "terminal": "4", "baggage": "12",
            },
        }

    def test_contains_flight_iata(self):
        result = _format_flight(self._sample_flight())
        assert "AI302" in result

    def test_contains_airline_name(self):
        result = _format_flight(self._sample_flight())
        assert "Air India" in result

    def test_contains_status_uppercase(self):
        result = _format_flight(self._sample_flight(status="active"))
        assert "ACTIVE" in result

    def test_contains_departure_airport(self):
        result = _format_flight(self._sample_flight())
        assert "DEL" in result

    def test_contains_arrival_airport(self):
        result = _format_flight(self._sample_flight())
        assert "LHR" in result

    def test_delay_180_triggers_eu261_warning(self):
        result = _format_flight(self._sample_flight(delay_dep=180))
        assert "EU261" in result or "3 hours" in result

    def test_delay_120_triggers_meals_warning(self):
        result = _format_flight(self._sample_flight(delay_dep=120))
        assert "meal" in result.lower() or "2 hours" in result.lower()

    def test_small_delay_no_warning(self):
        result = _format_flight(self._sample_flight(delay_dep=30))
        assert "EU261" not in result
        assert "meal" not in result.lower()

    def test_missing_aircraft_does_not_crash(self):
        flight = self._sample_flight()
        flight["aircraft"] = None
        result = _format_flight(flight)
        assert isinstance(result, str)

    def test_returns_string(self):
        assert isinstance(_format_flight(self._sample_flight()), str)


# ── FlightTool._run routing ───────────────────────────────────────────────────

class TestFlightToolRun:
    def test_status_prefix_calls_get_flight_status(self):
        with patch("src.tools.flight_tool.get_flight_status", return_value="status ok") as mock_fn:
            result = flight_tool._run("STATUS:AI302")
        mock_fn.assert_called_once_with("AI302")
        assert result == "status ok"

    def test_status_prefix_case_insensitive(self):
        with patch("src.tools.flight_tool.get_flight_status", return_value="ok") as mock_fn:
            flight_tool._run("status:AI302")
        mock_fn.assert_called_once_with("AI302")

    def test_alternatives_prefix_calls_get_alternatives(self):
        with patch("src.tools.flight_tool.get_alternative_flights", return_value="alt ok") as mock_fn:
            result = flight_tool._run("ALTERNATIVES:DEL,LHR")
        mock_fn.assert_called_once_with("DEL", "LHR")
        assert result == "alt ok"

    def test_alternatives_rejects_single_code(self):
        result = flight_tool._run("ALTERNATIVES:DEL")
        assert "Error" in result

    def test_plain_flight_code_calls_get_flight_status(self):
        with patch("src.tools.flight_tool.get_flight_status", return_value="ok") as mock_fn:
            flight_tool._run("AI302")
        mock_fn.assert_called_once_with("AI302")

    def test_run_returns_string(self):
        with patch("src.tools.flight_tool.get_flight_status", return_value="result"):
            result = flight_tool._run("STATUS:AI302")
        assert isinstance(result, str)

    def test_tool_name_exact(self):
        assert flight_tool.name == "Flight Status and Alternatives Tool"

    def test_tool_description_non_empty(self):
        assert len(flight_tool.description) > 50

    def test_singleton_is_flight_tool(self):
        assert isinstance(flight_tool, FlightTool)


# ── get_flight_status error handling ─────────────────────────────────────────

class TestGetFlightStatusErrors:
    def test_returns_string_when_flight_not_found(self):
        with patch("src.tools.flight_tool._aviationstack_flight", return_value=None):
            from src.tools.flight_tool import get_flight_status
            result = get_flight_status("ZZ999")
        assert isinstance(result, str)
        assert "ZZ999" in result

    def test_returns_string_on_api_exception(self):
        with patch("src.tools.flight_tool._aviationstack_flight", side_effect=Exception("timeout")):
            from src.tools.flight_tool import get_flight_status
            result = get_flight_status("AI302")
        assert isinstance(result, str)
        assert "AI302" in result


# ── get_alternative_flights ───────────────────────────────────────────────────

class TestGetAlternativeFlights:
    def test_returns_string_with_header(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [
            {
                "flight": {"iata": "BA141"},
                "departure": {"scheduled": "2024-01-15T14:00:00"},
                "arrival": {"scheduled": "2024-01-15T19:30:00"},
                "flight_status": "scheduled",
            }
        ]}
        mock_resp.raise_for_status = MagicMock()
        with patch("src.tools.flight_tool.requests.get", return_value=mock_resp):
            from src.tools.flight_tool import get_alternative_flights
            result = get_alternative_flights("DEL", "LHR")
        assert "DEL" in result
        assert "LHR" in result
        assert "BA141" in result

    def test_returns_no_flights_message_when_empty(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("src.tools.flight_tool.requests.get", return_value=mock_resp):
            from src.tools.flight_tool import get_alternative_flights
            result = get_alternative_flights("DEL", "LHR")
        assert "No" in result or "not found" in result.lower()

    def test_returns_string_on_exception(self):
        with patch("src.tools.flight_tool.requests.get", side_effect=Exception("network error")):
            from src.tools.flight_tool import get_alternative_flights
            result = get_alternative_flights("DEL", "LHR")
        assert isinstance(result, str)


# Need MagicMock in scope
from unittest.mock import MagicMock
