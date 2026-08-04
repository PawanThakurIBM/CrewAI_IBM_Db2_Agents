"""
Aircraft Task — verify aircraft readiness, MEL, fuel, and rotation cascade.
Context: depends on weather_task and flight_task outputs.
"""
from crewai import Task
from src.agents.aircraft_agent import aircraft_agent


def make_aircraft_task(weather_task: Task, flight_task: Task) -> Task:
    return Task(
        description=(
            "You have received outputs from the Weather Agent and the Flight Agent.\n\n"
            "The Flight Agent's output contains the aircraft tail number / registration. "
            "Use this to query the Fleet Management System Tool:\n"
            "1. Check the aircraft's airworthiness status\n"
            "2. Review active MEL (Minimum Equipment List) deferred defects\n"
            "3. Verify fuel state against mission fuel requirement\n"
            "4. Assess the rotation cascade impact — how many subsequent flights will be "
            "affected if this flight is further delayed?\n"
            "5. If the aircraft has issues or if delay impact is severe, search for a "
            "substitute aircraft using 'SUBSTITUTE'\n\n"
            "Consult IBM Db2 for aircraft maintenance manual and MEL dispatch procedures."
        ),
        expected_output=(
            "A structured aircraft status report containing:\n"
            "1. Aircraft registration, model, and age\n"
            "2. Airworthiness status: CLEAR or REVIEW REQUIRED\n"
            "3. Active MEL items (if any)\n"
            "4. Fuel on board vs. fuel required\n"
            "5. Dispatch recommendation: can this aircraft operate once conditions allow?\n"
            "6. Rotation cascade: number of subsequent flights affected and flight numbers\n"
            "7. Substitute aircraft recommendation if required (registration and availability)"
        ),
        agent=aircraft_agent,
        context=[weather_task, flight_task],
    )
