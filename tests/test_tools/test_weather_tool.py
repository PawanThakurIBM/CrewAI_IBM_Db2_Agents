"""
Exhaustive tests for WeatherTool.

Covers: IATA→city mapping, IATA→ICAO mapping, severity classifier,
_run() routing, error handling, OWM/METAR/TAF fetch failures.
No live HTTP calls — all requests are mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tools.weather_tool import (
    IATA_TO_CITY,
    IATA_TO_ICAO,
    WeatherTool,
    _city,
    _classify_severity,
    _icao,
    weather_tool,
)


# ── IATA mapping tests ────────────────────────────────────────────────────────

class TestIataToIcao:
    def test_del_maps_to_vidp(self):
        assert _icao("DEL") == "VIDP"

    def test_lhr_maps_to_egll(self):
        assert _icao("LHR") == "EGLL"

    def test_case_insensitive(self):
        assert _icao("del") == "VIDP"

    def test_unknown_iata_returns_uppercase_input(self):
        assert _icao("XYZ") == "XYZ"

    def test_all_known_iata_codes_present(self):
        for iata in ["DEL", "LHR", "LGW", "BOM", "DXB", "DOH", "FRA", "CDG", "AMS", "IST"]:
            assert iata in IATA_TO_ICAO


class TestIataToCity:
    def test_lhr_maps_to_london(self):
        assert _city("LHR") == "London"

    def test_del_maps_to_new_delhi(self):
        assert _city("DEL") == "New Delhi"

    def test_case_insensitive(self):
        assert _city("lhr") == "London"

    def test_unknown_iata_returns_uppercase(self):
        assert _city("XYZ") == "XYZ"

    def test_all_known_cities_non_empty(self):
        for iata, city in IATA_TO_CITY.items():
            assert city and len(city) > 0

    def test_lhr_and_lgw_both_map_to_london(self):
        assert _city("LHR") == "London"
        assert _city("LGW") == "London"


# ── Severity classifier ───────────────────────────────────────────────────────

class TestClassifySeverity:
    def test_thunderstorm_is_severe(self):
        assert _classify_severity(5, 9000, [210]) == "Severe"

    def test_extreme_weather_code_is_severe(self):
        assert _classify_severity(5, 9000, [900]) == "Severe"

    def test_heavy_rain_is_high(self):
        assert _classify_severity(5, 8000, [502]) == "High"

    def test_heavy_snow_is_high(self):
        assert _classify_severity(5, 8000, [602]) == "High"

    def test_low_visibility_is_high(self):
        assert _classify_severity(5, 1000, [800]) == "High"

    def test_strong_wind_is_high(self):
        assert _classify_severity(16, 10000, [800]) == "High"

    def test_medium_wind_is_medium(self):
        assert _classify_severity(11, 10000, [800]) == "Medium"

    def test_low_visibility_medium(self):
        assert _classify_severity(5, 3000, [800]) == "Medium"

    def test_clear_conditions_is_low(self):
        assert _classify_severity(3, 9999, [800]) == "Low"

    def test_empty_weather_ids_clear_is_low(self):
        assert _classify_severity(2, 10000, []) == "Low"


# ── WeatherTool._run routing ──────────────────────────────────────────────────

class TestWeatherToolRun:
    def _mock_get_weather(self, return_val: str = "weather ok"):
        return patch(
            "src.tools.weather_tool.get_weather_report",
            return_value=return_val,
        )

    def test_run_returns_string(self):
        with self._mock_get_weather():
            result = weather_tool._run("DEL,LHR")
        assert isinstance(result, str)

    def test_run_calls_get_weather_with_correct_iatas(self):
        with patch("src.tools.weather_tool.get_weather_report") as mock_gwr:
            mock_gwr.return_value = "ok"
            weather_tool._run("DEL,LHR")
            mock_gwr.assert_called_once_with("DEL", "LHR")

    def test_run_is_case_insensitive(self):
        with patch("src.tools.weather_tool.get_weather_report") as mock_gwr:
            mock_gwr.return_value = "ok"
            weather_tool._run("del,lhr")
            mock_gwr.assert_called_once_with("DEL", "LHR")

    def test_run_rejects_single_code(self):
        result = weather_tool._run("DEL")
        assert "Error" in result

    def test_run_rejects_three_codes(self):
        result = weather_tool._run("DEL,LHR,BOM")
        assert "Error" in result

    def test_run_returns_error_string_on_exception(self):
        with patch("src.tools.weather_tool.get_weather_report", side_effect=Exception("boom")):
            result = weather_tool._run("DEL,LHR")
        assert isinstance(result, str)
        assert "error" in result.lower() or "boom" in result.lower()

    def test_tool_name_is_correct(self):
        assert weather_tool.name == "Weather Information Tool"

    def test_tool_description_is_non_empty(self):
        assert len(weather_tool.description) > 50

    def test_singleton_is_weather_tool_instance(self):
        assert isinstance(weather_tool, WeatherTool)


# ── OWM fetch uses city names not IATA codes ──────────────────────────────────

class TestOwmUsesCityNames:
    """Critical regression test: OWM must receive city names, not IATA codes."""

    def test_owm_called_with_london_not_lhr(self):
        """Verifies the LHR→London fix — OWM rejects 'LHR' as a city name."""
        owm_calls = []

        def fake_owm(city: str) -> dict:
            owm_calls.append(city)
            return {
                "weather": [{"description": "clear sky", "id": 800}],
                "main": {"temp": 15.0},
                "wind": {"speed": 5.0},
                "visibility": 10000,
                "name": "London",
            }

        with patch("src.tools.weather_tool._owm_current", side_effect=fake_owm), \
             patch("src.tools.weather_tool._owm_forecast", return_value={"list": []}), \
             patch("src.tools.weather_tool._avwx_metar", return_value=[]), \
             patch("src.tools.weather_tool._avwx_taf", return_value=[]):
            weather_tool._run("DEL,LHR")

        assert "London" in owm_calls, f"Expected 'London' in OWM calls, got: {owm_calls}"
        assert "LHR" not in owm_calls, f"OWM was called with raw IATA 'LHR' — city mapping broken"

    def test_owm_called_with_new_delhi_not_del(self):
        owm_calls = []

        def fake_owm(city: str) -> dict:
            owm_calls.append(city)
            return {
                "weather": [{"description": "haze", "id": 721}],
                "main": {"temp": 32.0},
                "wind": {"speed": 3.0},
                "visibility": 4000,
                "name": "New Delhi",
            }

        with patch("src.tools.weather_tool._owm_current", side_effect=fake_owm), \
             patch("src.tools.weather_tool._owm_forecast", return_value={"list": []}), \
             patch("src.tools.weather_tool._avwx_metar", return_value=[]), \
             patch("src.tools.weather_tool._avwx_taf", return_value=[]):
            weather_tool._run("DEL,LHR")

        assert "New Delhi" in owm_calls
        assert "DEL" not in owm_calls


# ── get_weather_report error handling ─────────────────────────────────────────

class TestGetWeatherReportFallbacks:
    def test_owm_failure_does_not_crash(self):
        with patch("src.tools.weather_tool._owm_current", side_effect=Exception("timeout")), \
             patch("src.tools.weather_tool._owm_forecast", side_effect=Exception("timeout")), \
             patch("src.tools.weather_tool._avwx_metar", return_value=[]), \
             patch("src.tools.weather_tool._avwx_taf", return_value=[]):
            result = weather_tool._run("DEL,LHR")
        assert isinstance(result, str)
        assert "failed" in result.lower() or "error" in result.lower()

    def test_metar_failure_does_not_crash(self):
        fake_owm_resp = {
            "weather": [{"description": "clear sky", "id": 800}],
            "main": {"temp": 20.0},
            "wind": {"speed": 4.0},
            "visibility": 10000,
            "name": "London",
        }
        with patch("src.tools.weather_tool._owm_current", return_value=fake_owm_resp), \
             patch("src.tools.weather_tool._owm_forecast", return_value={"list": []}), \
             patch("src.tools.weather_tool._avwx_metar", side_effect=Exception("AVWX down")), \
             patch("src.tools.weather_tool._avwx_taf", return_value=[]):
            result = weather_tool._run("DEL,LHR")
        assert isinstance(result, str)
        assert "DEPARTURE" in result or "ARRIVAL" in result
