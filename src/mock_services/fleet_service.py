"""
Mock Fleet Management System.

Simulates internal airline fleet / aircraft management APIs (AMOS, SITA).
Returns aircraft airworthiness status, maintenance data, fuel state, and rotation schedule.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from crewai.tools import BaseTool

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AircraftRecord:
    registration: str       # e.g. VT-ANQ
    model: str              # e.g. Boeing 787-8
    msn: str                # manufacturer serial number
    age_years: float
    airworthy: bool
    mel_items: list[str]    # active Minimum Equipment List items (deferred defects)
    last_maintenance: date
    next_maintenance_due: date
    fuel_state_kg: int
    fuel_required_kg: int
    rotation: list[str]     # upcoming flights this aircraft is rostered for
    status_note: str

    def to_summary(self) -> str:
        mel_str = ", ".join(self.mel_items) if self.mel_items else "None"
        dispatch_ok = self.airworthy and not any("CRITICAL" in m for m in self.mel_items)
        lines = [
            f"## AIRCRAFT RECORD — {self.registration}",
            f"Model              : {self.model}",
            f"MSN                : {self.msn}",
            f"Age                : {self.age_years:.1f} years",
            f"Airworthy          : {'YES' if self.airworthy else 'NO ⚠'}",
            f"Active MEL Items   : {mel_str}",
            f"Last Maintenance   : {self.last_maintenance}",
            f"Next Maint Due     : {self.next_maintenance_due}",
            f"Days to Next Maint : {(self.next_maintenance_due - date.today()).days} days",
            f"Fuel On Board      : {self.fuel_state_kg:,} kg",
            f"Fuel Required      : {self.fuel_required_kg:,} kg",
            f"Fuel Sufficient    : {'YES' if self.fuel_state_kg >= self.fuel_required_kg else 'NO — ADDITIONAL FUELING REQUIRED'}",
            f"Dispatch Status    : {'CLEAR' if dispatch_ok else 'REVIEW REQUIRED'}",
            f"Rotation Schedule  : {' → '.join(self.rotation)}",
            f"Notes              : {self.status_note}",
        ]
        if len(self.rotation) > 1:
            lines.append(
                f"⚠ Delay Impact: This aircraft is rostered for {len(self.rotation)-1} subsequent "
                f"flight(s). A delay will propagate downstream."
            )
        return "\n".join(lines)


# ── Deterministic aircraft data keyed by registration prefix ─────────────────

_MODELS = [
    ("Boeing 787-8 Dreamliner", "B788"),
    ("Boeing 777-300ER", "B77W"),
    ("Airbus A320neo", "A20N"),
    ("Airbus A350-900", "A359"),
    ("Boeing 737-800", "B738"),
]

_MEL_POOL = [
    "APU inoperative (MEL 49-00-01) — ground start required",
    "IFE system row 12-18 inoperative (MEL 23-05-01)",
    "Window heat channel 2 inoperative (MEL 30-44-01)",
    "CRITICAL: Engine oil pressure sensor fault — maintenance inspection required",
    "Galley oven 2R inoperative (MEL 25-35-01)",
]


def _build_aircraft(registration: str) -> AircraftRecord:
    rng = random.Random(sum(ord(c) for c in registration))
    model_name, _ = rng.choice(_MODELS)
    age = round(rng.uniform(1.5, 12.0), 1)
    airworthy = rng.random() > 0.08  # 8% chance of AOG for demo variety
    mel_count = rng.randint(0, 2)
    mel_items = rng.sample(_MEL_POOL, k=min(mel_count, len(_MEL_POOL)))

    last_maint = date.today() - timedelta(days=rng.randint(10, 90))
    next_maint = date.today() + timedelta(days=rng.randint(5, 120))

    fuel_required = rng.randint(55000, 120000)
    fuel_state = int(fuel_required * rng.uniform(0.85, 1.15))

    rotations = ["AI302"]
    if rng.random() > 0.4:
        rotations.append(rng.choice(["AI303", "AI506", "AI210", "6E142", "UK702"]))
    if rng.random() > 0.7:
        rotations.append(rng.choice(["AI101", "AI880", "6E401"]))

    note = "No outstanding issues." if airworthy and not mel_items else \
           ("Aircraft on Ground — maintenance required." if not airworthy else
            f"{len(mel_items)} deferred MEL item(s) active — review before dispatch.")

    return AircraftRecord(
        registration=registration,
        model=model_name,
        msn=f"MSN-{rng.randint(30000, 65000)}",
        age_years=age,
        airworthy=airworthy,
        mel_items=mel_items,
        last_maintenance=last_maint,
        next_maintenance_due=next_maint,
        fuel_state_kg=fuel_state,
        fuel_required_kg=fuel_required,
        rotation=rotations,
        status_note=note,
    )


# ── Tail number lookup: flight IATA → registration ───────────────────────────

_FLIGHT_TO_REG: dict[str, str] = {
    "AI302": "VT-ANQ",
    "AI101": "VT-ALH",
    "AI506": "VT-ANB",
    "AI210": "VT-AKB",
    "6E142": "VT-IEX",
    "UK702": "VT-VJJ",
    "AI880": "VT-ANW",
}


def get_aircraft_status(query: str) -> str:
    """
    Return aircraft status by flight IATA or registration.
    """
    q = query.strip().upper()
    registration = _FLIGHT_TO_REG.get(q, q)  # if not found in map, treat as registration
    record = _build_aircraft(registration)
    logger.info("fleet_status_fetched", registration=registration)
    return record.to_summary()


def get_substitute_aircraft(model_hint: str = "") -> str:
    """Return available spare aircraft from the fleet."""
    spares = [
        _build_aircraft(reg)
        for reg in ["VT-ANR", "VT-ANS", "VT-ANT"]
        if _build_aircraft(reg).airworthy
    ]
    if not spares:
        return "No substitute aircraft currently available."
    lines = ["## AVAILABLE SUBSTITUTE AIRCRAFT"]
    for a in spares:
        fuel_ok = "✓" if a.fuel_state_kg >= a.fuel_required_kg else "⚠ Fuel top-up needed"
        lines.append(
            f"  {a.registration} | {a.model} | "
            f"MEL: {len(a.mel_items)} items | Fuel: {fuel_ok} | "
            f"Next Maint: {a.next_maintenance_due}"
        )
    return "\n".join(lines)


class FleetTool(BaseTool):
    name: str = "Fleet Management System Tool"
    description: str = (
        "Check aircraft airworthiness, maintenance status, fuel state, active MEL items, "
        "and rotation cascade impact for a given flight or aircraft registration. "
        "Also find available substitute aircraft. "
        "Supported input formats:\n"
        "  1. Aircraft for a flight : 'FLIGHT:AI302'\n"
        "  2. By registration       : 'REG:VT-ANQ'\n"
        "  3. Substitute aircraft   : 'SUBSTITUTE'\n"
    )

    def _run(self, query: str) -> str:
        logger.info("fleet_tool_called", input=query)
        q = query.strip().upper()
        if q == "SUBSTITUTE":
            return get_substitute_aircraft()
        if q.startswith("FLIGHT:"):
            flight = q.split(":", 1)[1].strip()
            return get_aircraft_status(flight)
        if q.startswith("REG:"):
            reg = q.split(":", 1)[1].strip()
            return get_aircraft_status(reg)
        # Fallback — treat raw input as flight code
        return get_aircraft_status(q)


fleet_tool = FleetTool()
