"""
Exhaustive tests for the mock Passenger Service.

Covers: Passenger dataclass, _build_manifest() determinism,
get_passenger_manifest(), PassengerServiceTool._run().
"""
from __future__ import annotations

import pytest

from src.mock_services.passenger_service import (
    Passenger,
    PassengerServiceTool,
    _build_manifest,
    get_passenger_manifest,
    passenger_service_tool,
)


# ── Passenger dataclass ───────────────────────────────────────────────────────

class TestPassenger:
    def _pax(self, cabin="ECONOMY", ffp_tier="NONE", special_codes=None):
        return Passenger(
            pnr="A12345", first_name="John", last_name="Smith",
            cabin=cabin, seat="42A", ffp_tier=ffp_tier,
            special_codes=special_codes or [],
        )

    def test_first_cabin_is_priority(self):
        assert self._pax(cabin="FIRST").is_priority()

    def test_business_cabin_is_priority(self):
        assert self._pax(cabin="BUSINESS").is_priority()

    def test_economy_gold_is_priority(self):
        assert self._pax(cabin="ECONOMY", ffp_tier="GOLD").is_priority()

    def test_economy_none_not_priority(self):
        assert not self._pax(cabin="ECONOMY", ffp_tier="NONE").is_priority()

    def test_special_codes_makes_priority(self):
        assert self._pax(cabin="ECONOMY", special_codes=["WCHR"]).is_priority()

    def test_to_dict_has_required_keys(self):
        d = self._pax().to_dict()
        for key in ["pnr", "name", "cabin", "seat", "ffp_tier", "special_codes", "priority"]:
            assert key in d

    def test_to_dict_priority_field_correct(self):
        assert self._pax(cabin="FIRST").to_dict()["priority"] is True
        assert self._pax(cabin="ECONOMY").to_dict()["priority"] is False

    def test_to_dict_name_is_full_name(self):
        d = self._pax().to_dict()
        assert "John" in d["name"] and "Smith" in d["name"]


# ── _build_manifest ───────────────────────────────────────────────────────────

class TestBuildManifest:
    def test_total_passengers_is_270(self):
        manifest = _build_manifest("AI302", seed=42)
        assert len(manifest) == 270

    def test_cabin_distribution_correct(self):
        manifest = _build_manifest("AI302", seed=42)
        cabins = {p.cabin for p in manifest}
        assert "FIRST" in cabins
        assert "BUSINESS" in cabins
        assert "ECONOMY" in cabins

    def test_first_class_count_is_8(self):
        manifest = _build_manifest("AI302", seed=42)
        assert len([p for p in manifest if p.cabin == "FIRST"]) == 8

    def test_business_count_is_24(self):
        manifest = _build_manifest("AI302", seed=42)
        assert len([p for p in manifest if p.cabin == "BUSINESS"]) == 24

    def test_deterministic_same_seed(self):
        m1 = _build_manifest("AI302", seed=100)
        m2 = _build_manifest("AI302", seed=100)
        assert [p.pnr for p in m1] == [p.pnr for p in m2]

    def test_different_seeds_produce_different_manifests(self):
        m1 = _build_manifest("AI302", seed=1)
        m2 = _build_manifest("AI302", seed=2)
        assert [p.pnr for p in m1] != [p.pnr for p in m2]

    def test_all_passengers_have_pnr(self):
        manifest = _build_manifest("AI302", seed=42)
        for p in manifest:
            assert p.pnr and len(p.pnr) > 0

    def test_all_passengers_have_cabin(self):
        manifest = _build_manifest("AI302", seed=42)
        for p in manifest:
            assert p.cabin in ("FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY")


# ── get_passenger_manifest ────────────────────────────────────────────────────

class TestGetPassengerManifest:
    def test_contains_flight_iata(self):
        result = get_passenger_manifest("AI302")
        assert "AI302" in result

    def test_contains_total_passengers(self):
        result = get_passenger_manifest("AI302")
        assert "270" in result

    def test_contains_cabin_breakdown(self):
        result = get_passenger_manifest("AI302")
        assert "FIRST" in result or "BUSINESS" in result

    def test_contains_priority_count(self):
        result = get_passenger_manifest("AI302")
        assert "Priority" in result

    def test_contains_special_assistance_section(self):
        result = get_passenger_manifest("AI302")
        assert "Special" in result

    def test_contains_at_risk_connections_section(self):
        result = get_passenger_manifest("AI302")
        assert "At-Risk" in result or "Connection" in result

    def test_deterministic_same_flight(self):
        r1 = get_passenger_manifest("AI302")
        r2 = get_passenger_manifest("AI302")
        assert r1 == r2

    def test_different_flights_may_differ(self):
        r1 = get_passenger_manifest("AI302")
        r2 = get_passenger_manifest("AI101")
        # Different flight codes → different seed → different manifest
        assert r1 != r2

    def test_case_insensitive(self):
        r1 = get_passenger_manifest("AI302")
        r2 = get_passenger_manifest("ai302")
        assert r1 == r2

    def test_returns_string(self):
        assert isinstance(get_passenger_manifest("AI302"), str)


# ── PassengerServiceTool._run ─────────────────────────────────────────────────

class TestPassengerServiceToolRun:
    def test_run_returns_manifest(self):
        result = passenger_service_tool._run("AI302")
        assert "AI302" in result
        assert "270" in result

    def test_strips_whitespace(self):
        result1 = passenger_service_tool._run("AI302")
        result2 = passenger_service_tool._run("  AI302  ")
        assert result1 == result2

    def test_uppercases_flight_code(self):
        result_lower = passenger_service_tool._run("ai302")
        result_upper = passenger_service_tool._run("AI302")
        assert result_lower == result_upper

    def test_returns_string(self):
        assert isinstance(passenger_service_tool._run("AI302"), str)

    def test_tool_name_correct(self):
        assert passenger_service_tool.name == "Passenger Service System Tool"

    def test_description_non_empty(self):
        assert len(passenger_service_tool.description) > 50

    def test_singleton_is_correct_type(self):
        assert isinstance(passenger_service_tool, PassengerServiceTool)
