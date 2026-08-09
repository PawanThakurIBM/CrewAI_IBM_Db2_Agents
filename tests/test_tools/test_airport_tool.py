"""
Exhaustive tests for AirportTool.

Covers: IATA→ICAO mapping, NOTAM severity parser, _run() input validation,
error handling for each fetch, full get_airport_status flow.
All HTTP calls are mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tools.airport_tool import (
    AirportTool,
    IATA_TO_ICAO,
    _icao,
    _parse_notam_severity,
    airport_tool,
    get_airport_status,
)


# ── IATA→ICAO mapping ─────────────────────────────────────────────────────────

class TestIataToIcao:
    def test_del_maps_to_vidp(self):
        assert _icao("DEL") == "VIDP"

    def test_lhr_maps_to_egll(self):
        assert _icao("LHR") == "EGLL"

    def test_case_insensitive(self):
        assert _icao("del") == "VIDP"

    def test_unknown_returns_uppercase(self):
        assert _icao("ZZZ") == "ZZZ"

    def test_all_known_codes_in_dict(self):
        for code in ["DEL", "LHR", "LGW", "BOM", "DXB", "DOH", "FRA", "CDG", "AMS", "IST"]:
            assert code in IATA_TO_ICAO


# ── NOTAM severity parser ─────────────────────────────────────────────────────

class TestParseNotamSeverity:
    def test_no_notams_returns_none_active(self):
        result = _parse_notam_severity([])
        assert "No active" in result

    def test_runway_closure_detected(self):
        notams = [{"text": "RWY 28L CLSD 1400-1800"}]
        result = _parse_notam_severity(notams)
        assert "RUNWAY CLOSURE" in result

    def test_non_closure_notams_return_count(self):
        notams = [{"text": "taxiway X closed"}, {"text": "lighting maintenance"}]
        result = _parse_notam_severity(notams)
        assert "2" in result

    def test_case_insensitive_closure_check(self):
        notams = [{"text": "rwy 09 clsd"}]
        result = _parse_notam_severity(notams)
        assert "RUNWAY CLOSURE" in result


# ── AirportTool._run input validation ─────────────────────────────────────────

class TestAirportToolRun:
    def test_valid_iata_calls_get_airport_status(self):
        with patch("src.tools.airport_tool.get_airport_status", return_value="status ok") as mock_fn:
            result = airport_tool._run("DEL")
        mock_fn.assert_called_once_with("DEL")
        assert result == "status ok"

    def test_lowercase_input_is_uppercased(self):
        with patch("src.tools.airport_tool.get_airport_status", return_value="ok") as mock_fn:
            airport_tool._run("del")
        mock_fn.assert_called_once_with("DEL")

    def test_rejects_two_letter_code(self):
        result = airport_tool._run("DE")
        assert "Error" in result

    def test_rejects_four_letter_code(self):
        result = airport_tool._run("EGLL")
        assert "Error" in result

    def test_rejects_empty_input(self):
        result = airport_tool._run("")
        assert "Error" in result

    def test_run_returns_string(self):
        with patch("src.tools.airport_tool.get_airport_status", return_value="result"):
            result = airport_tool._run("LHR")
        assert isinstance(result, str)

    def test_tool_name_exact(self):
        assert airport_tool.name == "Airport Operations and NOTAM Tool"

    def test_description_non_empty(self):
        assert len(airport_tool.description) > 50

    def test_singleton_is_airport_tool(self):
        assert isinstance(airport_tool, AirportTool)


# ── get_airport_status integration ────────────────────────────────────────────

class TestGetAirportStatus:
    def _mock_meta(self):
        return {
            "airport_name": "Indira Gandhi International",
            "country_name": "India",
            "timezone": "Asia/Kolkata",
            "latitude": "28.5665",
            "longitude": "77.1031",
        }

    def test_contains_airport_header(self):
        with patch("src.tools.airport_tool._fetch_airport_meta", return_value=self._mock_meta()), \
             patch("src.tools.airport_tool._fetch_notams", return_value=[]):
            result = get_airport_status("DEL")
        assert "DEL" in result
        assert "VIDP" in result

    def test_contains_notam_status(self):
        with patch("src.tools.airport_tool._fetch_airport_meta", return_value=None), \
             patch("src.tools.airport_tool._fetch_notams", return_value=[]):
            result = get_airport_status("DEL")
        assert "NOTAM" in result

    def test_notam_list_shown_when_present(self):
        notams = [{"traditionalMessage": "RWY 28L CLSD 1400-1800"}]
        with patch("src.tools.airport_tool._fetch_airport_meta", return_value=None), \
             patch("src.tools.airport_tool._fetch_notams", return_value=notams):
            result = get_airport_status("DEL")
        assert "RWY 28L" in result

    def test_meta_fetch_failure_does_not_crash(self):
        with patch("src.tools.airport_tool._fetch_airport_meta", side_effect=Exception("timeout")), \
             patch("src.tools.airport_tool._fetch_notams", return_value=[]):
            result = get_airport_status("DEL")
        assert isinstance(result, str)
        assert "DEL" in result

    def test_notam_fetch_failure_does_not_crash(self):
        with patch("src.tools.airport_tool._fetch_airport_meta", return_value=self._mock_meta()), \
             patch("src.tools.airport_tool._fetch_notams", side_effect=Exception("AVWX down")):
            result = get_airport_status("LHR")
        assert isinstance(result, str)
        assert "LHR" in result

    def test_returns_string(self):
        with patch("src.tools.airport_tool._fetch_airport_meta", return_value=None), \
             patch("src.tools.airport_tool._fetch_notams", return_value=[]):
            result = get_airport_status("BOM")
        assert isinstance(result, str)
