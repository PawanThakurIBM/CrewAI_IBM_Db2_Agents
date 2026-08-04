"""
Flight Task — fetch real-time flight status and identify alternatives.
Context: receives the raw user request.
"""
from crewai import Task
from src.agents.flight_agent import flight_agent


def make_flight_task(flight_query: str) -> Task:
    return Task(
        description=(
            f"You have received the following flight delay report:\n\n"
            f"{flight_query}\n\n"
            "Using the Flight Status and Alternatives Tool:\n"
            "1. Fetch the real-time status of the flight mentioned (e.g., STATUS:AI302)\n"
            "2. Note the aircraft tail number / registration from the status response\n"
            "3. Check the delay duration and the official IATA delay reason code\n"
            "4. Identify the previous leg flown by this aircraft (if delay is propagated)\n"
            "5. Search for alternative flights on this route (e.g., ALTERNATIVES:DEL,LHR)\n"
            "6. Consult IBM Db2 for flight operations SOP and IATA delay code definitions\n\n"
            "Extract the departure and arrival IATA codes from the flight report."
        ),
        expected_output=(
            "A structured flight operations report containing:\n"
            "1. Flight number, airline, current status (DELAYED/CANCELLED/DIVERTED)\n"
            "2. Aircraft registration / tail number\n"
            "3. Scheduled vs estimated departure and arrival times\n"
            "4. Delay duration in minutes\n"
            "5. Official IATA delay code and reason\n"
            "6. Previous leg history (on-time or delayed)\n"
            "7. List of top 3-5 alternative flights with departure times and seat availability\n"
            "8. Operational recommendation: delay / divert / cancel / proceed"
        ),
        agent=flight_agent,
    )
