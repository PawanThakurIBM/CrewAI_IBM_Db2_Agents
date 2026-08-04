"""
Mock Passenger Service System (PSS).

Simulates Amadeus Altéa / Sabre passenger manifest APIs.
Returns a realistic passenger manifest for a given flight.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from crewai.tools import BaseTool

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class Passenger:
    pnr: str
    first_name: str
    last_name: str
    cabin: str              # FIRST / BUSINESS / PREMIUM_ECONOMY / ECONOMY
    seat: str
    ffp_tier: str           # GOLD / SILVER / BRONZE / NONE
    special_codes: list[str] = field(default_factory=list)  # WCHR, UM, BLND, MEDA, etc.
    onward_flight: Optional[str] = None
    onward_connection_minutes: int = 0  # connection buffer at destination

    def is_priority(self) -> bool:
        return (
            self.cabin in ("FIRST", "BUSINESS")
            or self.ffp_tier == "GOLD"
            or bool(self.special_codes)
        )

    def to_dict(self) -> dict:
        return {
            "pnr": self.pnr,
            "name": f"{self.first_name} {self.last_name}",
            "cabin": self.cabin,
            "seat": self.seat,
            "ffp_tier": self.ffp_tier,
            "special_codes": self.special_codes,
            "onward_flight": self.onward_flight,
            "onward_connection_minutes": self.onward_connection_minutes,
            "priority": self.is_priority(),
        }


# ── Deterministic seed data keyed by flight IATA ─────────────────────────────

_FIRST_NAMES = ["Arjun", "Priya", "James", "Sophie", "Mohammed", "Amelia",
                "Ravi", "Emily", "Chen", "Laura", "David", "Fatima", "Carlos",
                "Anna", "Kenji", "Sara", "Luca", "Aisha", "Tom", "Neha"]
_LAST_NAMES  = ["Sharma", "Patel", "Smith", "Johnson", "Ali", "Brown",
                "Kumar", "Williams", "Wang", "Taylor", "Jones", "Khalid",
                "Rossi", "Novak", "Tanaka", "Ahmed", "Ferrari", "Osei",
                "Müller", "Singh"]
_SPECIAL_CODES_POOL = ["WCHR", "UM", "BLND", "DEAF", "MEDA", "INFT", "DPNA"]
_ONWARD_FLIGHTS = [None, None, None, "BA178", "LH760", "EK006", "QR007"]


def _build_manifest(flight_iata: str, seed: int) -> list[Passenger]:
    rng = random.Random(seed)
    passengers: list[Passenger] = []

    cabin_distribution = [
        ("FIRST", 8),
        ("BUSINESS", 24),
        ("PREMIUM_ECONOMY", 18),
        ("ECONOMY", 220),
    ]

    seat_counters = {"FIRST": 1, "BUSINESS": 10, "PREMIUM_ECONOMY": 20, "ECONOMY": 40}
    seat_row_map  = {"FIRST": "A", "BUSINESS": "D", "PREMIUM_ECONOMY": "G", "ECONOMY": "J"}

    for cabin, count in cabin_distribution:
        for _ in range(count):
            fn = rng.choice(_FIRST_NAMES)
            ln = rng.choice(_LAST_NAMES)
            pnr = f"{rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{rng.randint(10000,99999)}"

            ffp_weights = {"FIRST": ["GOLD", "SILVER"], "BUSINESS": ["GOLD", "SILVER", "BRONZE"],
                           "PREMIUM_ECONOMY": ["BRONZE", "NONE", "NONE"],
                           "ECONOMY": ["NONE", "NONE", "NONE", "BRONZE"]}
            tier = rng.choice(ffp_weights[cabin])

            specials: list[str] = []
            if rng.random() < 0.06:  # ~6% have special needs
                specials = rng.sample(_SPECIAL_CODES_POOL, k=rng.randint(1, 2))

            row = seat_counters[cabin]
            col = rng.choice("ABCDEF")
            seat_counters[cabin] += 1
            seat = f"{row}{col}"

            onward = rng.choice(_ONWARD_FLIGHTS)
            connection_mins = rng.randint(40, 90) if onward else 0

            passengers.append(Passenger(
                pnr=pnr,
                first_name=fn,
                last_name=ln,
                cabin=cabin,
                seat=seat,
                ffp_tier=tier,
                special_codes=specials,
                onward_flight=onward,
                onward_connection_minutes=connection_mins,
            ))

    return passengers


def get_passenger_manifest(flight_iata: str) -> str:
    """
    Return a formatted passenger manifest report for the given flight.
    Seed is derived from the flight code for deterministic (but realistic) data.
    """
    seed = sum(ord(c) for c in flight_iata.upper())
    manifest = _build_manifest(flight_iata.upper(), seed)

    total = len(manifest)
    priority = [p for p in manifest if p.is_priority()]
    special = [p for p in manifest if p.special_codes]
    at_risk = [p for p in manifest if p.onward_flight and p.onward_connection_minutes < 70]

    cabin_counts = {}
    for p in manifest:
        cabin_counts[p.cabin] = cabin_counts.get(p.cabin, 0) + 1

    lines = [
        f"## PASSENGER MANIFEST — Flight {flight_iata.upper()}",
        f"Total Passengers : {total}",
        "",
        "Cabin Breakdown:",
        *[f"  {cab:<18}: {cnt}" for cab, cnt in cabin_counts.items()],
        "",
        f"Priority Passengers (First/Business/Gold/Special) : {len(priority)}",
        f"Special Assistance (WCHR/UM/MEDA/etc.)            : {len(special)}",
        f"At-Risk Connections (<70 min buffer)               : {len(at_risk)}",
        "",
        "Special Assistance Detail:",
    ]
    for p in special[:10]:
        lines.append(f"  {p.pnr} | {p.first_name} {p.last_name} | {p.cabin} | Codes: {', '.join(p.special_codes)}")

    lines += [
        "",
        "At-Risk Connection Passengers:",
    ]
    for p in at_risk[:10]:
        lines.append(
            f"  {p.pnr} | {p.first_name} {p.last_name} | {p.cabin} | "
            f"Onward: {p.onward_flight} | Buffer: {p.onward_connection_minutes} min"
        )

    lines += [
        "",
        "Top Priority Passengers (VIP / First / Gold):",
    ]
    vip = [p for p in priority if p.cabin in ("FIRST", "BUSINESS") or p.ffp_tier == "GOLD"]
    for p in vip[:10]:
        lines.append(f"  {p.pnr} | {p.first_name} {p.last_name} | {p.cabin} | {p.ffp_tier}")

    logger.info("manifest_generated", flight=flight_iata, total=total, priority=len(priority))
    return "\n".join(lines)


class PassengerServiceTool(BaseTool):
    name: str = "Passenger Service System Tool"
    description: str = (
        "Retrieve the full passenger manifest for a given flight, including cabin breakdown, "
        "VIP and priority passengers, special assistance codes (WCHR, UM, MEDA, INFT), "
        "and passengers with tight onward connections at risk of misconnection. "
        "Input: flight IATA code, e.g. 'AI302'. "
        "Returns structured passenger manifest report."
    )

    def _run(self, flight_iata: str) -> str:
        logger.info("passenger_tool_called", flight=flight_iata)
        return get_passenger_manifest(flight_iata.strip().upper())


passenger_service_tool = PassengerServiceTool()
