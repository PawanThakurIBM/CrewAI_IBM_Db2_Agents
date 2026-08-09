"""
Exhaustive tests for the mock Fleet Service.

Covers: AircraftRecord.to_summary(), _build_aircraft() determinism,
get_aircraft_status(), get_substitute_aircraft(), FleetTool._run() routing.
"""
from __future__ import annotations

import pytest

from src.mock_services.fleet_service import (
    AircraftRecord,
    FleetTool,
    _FLIGHT_TO_REG,
    _build_aircraft,
    fleet_tool,
    get_aircraft_status,
    get_substitute_aircraft,
)


# ── AircraftRecord.to_summary ─────────────────────────────────────────────────

class TestAircraftRecordToSummary:
    def _record(self, airworthy=True, mel_items=None, rotation=None):
        from datetime import date, timedelta
        return AircraftRecord(
            registration="VT-ANQ",
            model="Boeing 787-8",
            msn="MSN-40001",
            age_years=5.2,
            airworthy=airworthy,
            mel_items=mel_items or [],
            last_maintenance=date.today() - timedelta(days=30),
            next_maintenance_due=date.today() + timedelta(days=60),
            fuel_state_kg=90000,
            fuel_required_kg=80000,
            rotation=rotation or ["AI302"],
            status_note="No outstanding issues.",
        )

    def test_contains_registration(self):
        assert "VT-ANQ" in self._record().to_summary()

    def test_airworthy_yes(self):
        assert "YES" in self._record(airworthy=True).to_summary()

    def test_not_airworthy_shows_warning(self):
        summary = self._record(airworthy=False).to_summary()
        assert "NO" in summary

    def test_mel_items_listed(self):
        summary = self._record(mel_items=["APU inoperative"]).to_summary()
        assert "APU" in summary

    def test_no_mel_items_shows_none(self):
        assert "None" in self._record(mel_items=[]).to_summary()

    def test_fuel_sufficient_yes(self):
        assert "YES" in self._record().to_summary()

    def test_multiple_rotations_show_cascade_warning(self):
        summary = self._record(rotation=["AI302", "AI303", "AI506"]).to_summary()
        assert "propagate" in summary.lower() or "downstream" in summary.lower()

    def test_single_rotation_no_cascade_warning(self):
        summary = self._record(rotation=["AI302"]).to_summary()
        assert "propagate" not in summary.lower()

    def test_returns_string(self):
        assert isinstance(self._record().to_summary(), str)


# ── _build_aircraft determinism ───────────────────────────────────────────────

class TestBuildAircraft:
    def test_same_reg_produces_same_result(self):
        r1 = _build_aircraft("VT-ANQ")
        r2 = _build_aircraft("VT-ANQ")
        assert r1.registration == r2.registration
        assert r1.model == r2.model
        assert r1.fuel_state_kg == r2.fuel_state_kg

    def test_different_regs_may_differ(self):
        r1 = _build_aircraft("VT-ANQ")
        r2 = _build_aircraft("VT-ALH")
        # Not guaranteed to differ on all fields but registration always differs
        assert r1.registration != r2.registration

    def test_airworthy_is_boolean(self):
        r = _build_aircraft("VT-ANQ")
        assert isinstance(r.airworthy, bool)

    def test_fuel_state_is_positive(self):
        r = _build_aircraft("VT-ANQ")
        assert r.fuel_state_kg > 0

    def test_rotation_is_non_empty_list(self):
        r = _build_aircraft("VT-ANQ")
        assert isinstance(r.rotation, list)
        assert len(r.rotation) >= 1


# ── get_aircraft_status ───────────────────────────────────────────────────────

class TestGetAircraftStatus:
    def test_known_flight_resolves_registration(self):
        result = get_aircraft_status("AI302")
        assert "VT-ANQ" in result

    def test_direct_registration_works(self):
        result = get_aircraft_status("VT-ANQ")
        assert "VT-ANQ" in result

    def test_returns_string(self):
        assert isinstance(get_aircraft_status("AI302"), str)

    def test_contains_dispatch_status(self):
        result = get_aircraft_status("AI302")
        assert "CLEAR" in result or "REVIEW" in result

    def test_all_known_flights_resolve(self):
        for flight in _FLIGHT_TO_REG:
            result = get_aircraft_status(flight)
            assert isinstance(result, str) and len(result) > 50


# ── get_substitute_aircraft ───────────────────────────────────────────────────

class TestGetSubstituteAircraft:
    def test_returns_string(self):
        assert isinstance(get_substitute_aircraft(), str)

    def test_contains_registration_or_no_available(self):
        result = get_substitute_aircraft()
        assert "VT-" in result or "No substitute" in result


# ── FleetTool._run routing ────────────────────────────────────────────────────

class TestFleetToolRun:
    def test_flight_prefix(self):
        result = fleet_tool._run("FLIGHT:AI302")
        assert "VT-ANQ" in result

    def test_reg_prefix(self):
        result = fleet_tool._run("REG:VT-ANQ")
        assert "VT-ANQ" in result

    def test_substitute_command(self):
        result = fleet_tool._run("SUBSTITUTE")
        assert isinstance(result, str)

    def test_plain_input_treated_as_flight(self):
        result = fleet_tool._run("AI302")
        assert isinstance(result, str)

    def test_case_insensitive_flight_prefix(self):
        result = fleet_tool._run("flight:AI302")
        assert "VT-ANQ" in result

    def test_returns_string(self):
        assert isinstance(fleet_tool._run("FLIGHT:AI302"), str)

    def test_tool_name_correct(self):
        assert fleet_tool.name == "Fleet Management System Tool"

    def test_singleton_is_fleet_tool(self):
        assert isinstance(fleet_tool, FleetTool)
