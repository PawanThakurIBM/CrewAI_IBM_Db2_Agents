"""
Exhaustive tests for the mock Booking Service.

Covers: FlightOption.to_summary(), get_available_flights(), generate_rebooking_plan(),
BookingTool._run() routing and input validation.
"""
from __future__ import annotations

import pytest

from src.mock_services.booking_service import (
    BookingTool,
    FlightOption,
    _ALTERNATIVE_FLIGHTS,
    _DEFAULT_OPTIONS,
    booking_tool,
    generate_rebooking_plan,
    get_available_flights,
)


# ── FlightOption.to_summary ───────────────────────────────────────────────────

class TestFlightOptionToSummary:
    def _option(self, codeshare=False, partner=None):
        return FlightOption("AI302A", "DEL", "LHR", "16:30", "21:45",
                            "B788", 4, 12, 8, 120, codeshare, partner)

    def test_contains_flight_iata(self):
        assert "AI302A" in self._option().to_summary()

    def test_contains_seat_counts(self):
        summary = self._option().to_summary()
        assert "F:4" in summary
        assert "J:12" in summary

    def test_codeshare_shows_partner(self):
        summary = self._option(codeshare=True, partner="EK").to_summary()
        assert "codeshare" in summary.lower()
        assert "EK" in summary

    def test_non_codeshare_no_partner_text(self):
        summary = self._option(codeshare=False).to_summary()
        assert "codeshare" not in summary.lower()

    def test_returns_string(self):
        assert isinstance(self._option().to_summary(), str)


# ── get_available_flights ─────────────────────────────────────────────────────

class TestGetAvailableFlights:
    def test_del_lhr_returns_known_flights(self):
        result = get_available_flights("DEL", "LHR")
        assert "BA141" in result or "AI302A" in result

    def test_lhr_del_returns_known_flights(self):
        result = get_available_flights("LHR", "DEL")
        assert "AI301" in result or "BA142" in result

    def test_unknown_route_returns_default_options(self):
        result = get_available_flights("AAA", "BBB")
        assert isinstance(result, str)
        assert "AAA" in result or "BBB" in result

    def test_case_insensitive_same_flights_returned(self):
        result_upper = get_available_flights("DEL", "LHR")
        result_lower = get_available_flights("del", "lhr")
        # Header differs (raw input preserved) but flight data must be identical
        assert "AI302A" in result_upper and "AI302A" in result_lower
        assert "BA141" in result_upper and "BA141" in result_lower

    def test_contains_priority_guidelines(self):
        result = get_available_flights("DEL", "LHR")
        assert "Priority" in result or "FIRST" in result

    def test_returns_string(self):
        assert isinstance(get_available_flights("DEL", "LHR"), str)

    def test_header_contains_route(self):
        result = get_available_flights("DEL", "LHR")
        assert "DEL" in result and "LHR" in result

    def test_all_known_routes_present(self):
        for route in _ALTERNATIVE_FLIGHTS:
            origin, dest = route.split("-")
            result = get_available_flights(origin, dest)
            assert isinstance(result, str) and len(result) > 50


# ── generate_rebooking_plan ───────────────────────────────────────────────────

class TestGenerateRebookingPlan:
    def test_contains_flight_iata(self):
        result = generate_rebooking_plan("AI302", "DEL", "LHR")
        assert "AI302" in result

    def test_contains_total_passengers(self):
        result = generate_rebooking_plan("AI302", "DEL", "LHR")
        assert "270" in result

    def test_contains_rebooking_sections(self):
        result = generate_rebooking_plan("AI302", "DEL", "LHR")
        assert "FIRST" in result or "BUSINESS" in result
        assert "ECONOMY" in result

    def test_contains_completion_estimate(self):
        result = generate_rebooking_plan("AI302", "DEL", "LHR")
        assert "COMPLETION" in result or "minutes" in result.lower()

    def test_deterministic_same_flight(self):
        r1 = generate_rebooking_plan("AI302", "DEL", "LHR")
        r2 = generate_rebooking_plan("AI302", "DEL", "LHR")
        assert r1 == r2

    def test_returns_string(self):
        assert isinstance(generate_rebooking_plan("AI302", "DEL", "LHR"), str)


# ── BookingTool._run routing ──────────────────────────────────────────────────

class TestBookingToolRun:
    def test_flights_prefix_calls_get_available(self):
        result = booking_tool._run("FLIGHTS:DEL,LHR")
        assert isinstance(result, str)
        assert "DEL" in result or "LHR" in result

    def test_rebook_prefix_calls_rebooking_plan(self):
        result = booking_tool._run("REBOOK:AI302,DEL,LHR")
        assert isinstance(result, str)
        assert "AI302" in result

    def test_flights_rejects_single_arg(self):
        result = booking_tool._run("FLIGHTS:DEL")
        assert "Error" in result

    def test_rebook_rejects_two_args(self):
        result = booking_tool._run("REBOOK:AI302,DEL")
        assert "Error" in result

    def test_unknown_command_returns_error(self):
        result = booking_tool._run("STATUS:AI302")
        assert "Error" in result or "unknown" in result.lower()

    def test_case_insensitive_prefix(self):
        result = booking_tool._run("flights:DEL,LHR")
        assert "DEL" in result or "Error" not in result

    def test_returns_string(self):
        assert isinstance(booking_tool._run("FLIGHTS:DEL,LHR"), str)

    def test_tool_name_correct(self):
        assert booking_tool.name == "Booking and Seat Inventory Tool"

    def test_singleton_is_booking_tool(self):
        assert isinstance(booking_tool, BookingTool)
