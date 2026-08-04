"""
Passenger Task — retrieve manifest and identify priority/at-risk passengers.
Context: receives the raw user request.
"""
from crewai import Task
from src.agents.passenger_agent import passenger_agent


def make_passenger_task(flight_query: str) -> Task:
    return Task(
        description=(
            f"You have received the following flight delay report:\n\n"
            f"{flight_query}\n\n"
            "Using the Passenger Service System Tool, retrieve the full passenger manifest "
            "for the flight mentioned in the report (e.g., AI302). "
            "Then consult the IBM Db2 Enterprise Knowledge Search for the airline's "
            "passenger handling policy and special assistance procedures.\n\n"
            "Identify:\n"
            "- Total passenger count and cabin class breakdown\n"
            "- VIP, Gold FFP, and premium cabin passengers\n"
            "- Passengers with special assistance codes (WCHR, UM, MEDA, INFT, BLND, DEAF)\n"
            "- Passengers with onward connections at risk of misconnection\n"
            "- Any passengers who should be prioritised for immediate action"
        ),
        expected_output=(
            "A structured passenger manifest report containing:\n"
            "1. Total passengers and cabin class breakdown (First / Business / Premium Economy / Economy)\n"
            "2. Number of priority passengers (VIP, Gold, First/Business cabin)\n"
            "3. Special assistance passengers list with codes\n"
            "4. Passengers with at-risk connections (connection buffer < 70 min)\n"
            "5. Recommended priority order for rebooking\n"
            "6. Any immediate welfare actions required (meals, wheelchairs, guardian contact for UMs)"
        ),
        agent=passenger_agent,
    )
