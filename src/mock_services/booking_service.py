"""
Mock Booking System / Seat Inventory Service.

Simulates Amadeus / Sabre / Travelport seat inventory and rebooking APIs.
Returns seat availability on alternative flights and handles rebooking logic.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from crewai.tools import BaseTool

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FlightOption:
    flight_iata: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    aircraft_type: str
    seats_first: int
    seats_business: int
    seats_premium_economy: int
    seats_economy: int
    codeshare: bool
    partner_airline: Optional[str] = None

    def to_summary(self) -> str:
        partner = f" (codeshare: {self.partner_airline})" if self.codeshare else ""
        return (
            f"{self.flight_iata}{partner} | "
            f"Dep: {self.departure_time} → Arr: {self.arrival_time} | "
            f"Seats — F:{self.seats_first} J:{self.seats_business} "
            f"W:{self.seats_premium_economy} Y:{self.seats_economy}"
        )


# ── Deterministic alternative flight data ─────────────────────────────────────

_ALTERNATIVE_FLIGHTS: dict[str, list[FlightOption]] = {
    "DEL-LHR": [
        FlightOption("AI302A", "DEL", "LHR", "16:30", "21:45", "B788", 4, 12, 8, 120,
                     False),
        FlightOption("BA141",  "DEL", "LHR", "01:55", "07:30", "B777", 8, 18, 24, 220,
                     False),
        FlightOption("EK509",  "DEL", "DXB", "10:00", "12:10", "B77W", 6, 20, 0, 180,
                     True, "EK"),   # DEL→DXB→LHR connection
        FlightOption("QR574",  "DEL", "DOH", "06:05", "08:30", "A350", 4, 16, 0, 210,
                     True, "QR"),   # DEL→DOH→LHR connection
        FlightOption("LH761",  "DEL", "FRA", "04:35", "08:25", "A340", 4, 22, 0, 250,
                     True, "LH"),   # DEL→FRA→LHR connection
    ],
    "LHR-DEL": [
        FlightOption("AI301",  "LHR", "DEL", "14:00", "03:30+1", "B788", 4, 12, 8, 120,
                     False),
        FlightOption("BA142",  "LHR", "DEL", "21:30", "11:50+1", "B777", 8, 18, 24, 220,
                     False),
        FlightOption("EK012",  "LHR", "DXB", "08:00", "18:30", "A380", 14, 76, 0, 426,
                     True, "EK"),
    ],
}

_DEFAULT_OPTIONS: list[FlightOption] = [
    FlightOption("OPT001", "??", "??", "TBD", "TBD", "B738", 0, 8, 12, 80, False),
]


def get_available_flights(origin: str, destination: str) -> str:
    """Return available alternative flights for a given city pair."""
    key = f"{origin.upper()}-{destination.upper()}"
    options = _ALTERNATIVE_FLIGHTS.get(key, _DEFAULT_OPTIONS)

    lines = [f"## AVAILABLE ALTERNATIVE FLIGHTS: {origin} → {destination}"]
    if not options:
        return f"No alternative flights found for {origin} → {destination}."

    for i, opt in enumerate(options, 1):
        lines.append(f"{i}. {opt.to_summary()}")

    lines += [
        "",
        "Rebooking Priority Guidelines:",
        "  1. FIRST/BUSINESS class + Gold FFP members → first available seats in same/higher cabin",
        "  2. Unaccompanied Minors (UM) → confirmed on next available flight, guardian notified",
        "  3. Medical (MEDA) / Wheelchair (WCHR) → confirmed, special services pre-arranged",
        "  4. At-risk connections → prioritise flights with sufficient connection time",
        "  5. Economy passengers → rebooking on next available with confirmed seat",
    ]
    return "\n".join(lines)


def generate_rebooking_plan(flight_iata: str, origin: str, destination: str) -> str:
    """
    Generate a full rebooking plan for a disrupted flight.
    """
    rng = random.Random(sum(ord(c) for c in flight_iata))
    key = f"{origin.upper()}-{destination.upper()}"
    options = _ALTERNATIVE_FLIGHTS.get(key, _DEFAULT_OPTIONS)

    total_pax = 270
    first_pax = 8
    biz_pax = 24
    prem_pax = 18
    eco_pax = 220
    special_pax = int(total_pax * 0.06)
    at_risk_pax = int(total_pax * 0.12)

    plan_lines = [
        f"## REBOOKING PLAN — Flight {flight_iata}",
        f"Affected Passengers: {total_pax}",
        "",
        "RECOMMENDED ALLOCATION:",
    ]

    for cabin, count, pref_idx in [
        ("FIRST / BUSINESS", first_pax + biz_pax, 0),
        ("PREMIUM ECONOMY",  prem_pax, 0),
        ("ECONOMY",          eco_pax, 1),
    ]:
        if options:
            opt = options[min(pref_idx, len(options) - 1)]
            plan_lines.append(
                f"  {cabin:<22}: {count:>3} pax → {opt.flight_iata} "
                f"(dep {opt.departure_time})"
            )

    plan_lines += [
        "",
        f"Special Assistance ({special_pax} pax): Confirm manually — notify ground services at destination.",
        f"At-risk Connections ({at_risk_pax} pax): Endorsed to partner airlines where possible.",
        "",
        "ESTIMATED COMPLETION: 90–120 minutes from authorization.",
        "STAFF REQUIRED: 4 customer service agents + 1 supervisor.",
    ]

    logger.info("rebooking_plan_generated", flight=flight_iata, total_pax=total_pax)
    return "\n".join(plan_lines)


class BookingTool(BaseTool):
    name: str = "Booking and Seat Inventory Tool"
    description: str = (
        "Search for available alternative flights and generate rebooking plans for disrupted passengers. "
        "Supported input formats:\n"
        "  1. Available flights     : 'FLIGHTS:DEL,LHR'\n"
        "  2. Full rebooking plan   : 'REBOOK:AI302,DEL,LHR'\n"
    )

    def _run(self, query: str) -> str:
        logger.info("booking_tool_called", input=query)
        q = query.strip().upper()
        if q.startswith("FLIGHTS:"):
            pair = q.split(":", 1)[1].strip()
            parts = [p.strip() for p in pair.split(",")]
            if len(parts) != 2:
                return "Error: FLIGHTS expects 'ORIGIN,DESTINATION' e.g. 'DEL,LHR'."
            return get_available_flights(parts[0], parts[1])
        elif q.startswith("REBOOK:"):
            args = q.split(":", 1)[1].strip()
            parts = [p.strip() for p in args.split(",")]
            if len(parts) != 3:
                return "Error: REBOOK expects 'FLIGHT,ORIGIN,DESTINATION' e.g. 'AI302,DEL,LHR'."
            return generate_rebooking_plan(parts[0], parts[1], parts[2])
        return "Error: unknown command. Use FLIGHTS:DEL,LHR or REBOOK:AI302,DEL,LHR."


booking_tool = BookingTool()
