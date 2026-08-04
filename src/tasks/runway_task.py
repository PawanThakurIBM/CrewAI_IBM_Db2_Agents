"""
Runway Task — assess airport/runway operational status.
Context: depends on weather_task and flight_task outputs.
"""
from crewai import Task
from src.agents.runway_agent import runway_agent


def make_runway_task(weather_task: Task, flight_task: Task) -> Task:
    return Task(
        description=(
            "You have received outputs from the Weather Agent and the Flight Agent.\n\n"
            "Using the Airport Operations and NOTAM Tool:\n"
            "1. Check the NOTAM status and runway availability for the DEPARTURE airport\n"
            "2. Check the NOTAM status and runway availability for the ARRIVAL airport\n"
            "3. Check conditions at the primary alternate airport if weather severity is High or Severe\n\n"
            "Use the Weather Agent's output to understand current visibility, wind, and "
            "precipitation at each airport. Use the Flight Agent's output to identify which "
            "airports are in scope.\n\n"
            "Consult IBM Db2 for airport operations manual, runway condition codes (RCAM), "
            "and ground operations procedures."
        ),
        expected_output=(
            "A structured airport and runway status report containing:\n"
            "1. Departure airport: runway status (operational / restricted / closed), active NOTAMs\n"
            "2. Arrival airport: runway status, active NOTAMs, any approach restrictions\n"
            "3. Gate availability at destination\n"
            "4. De-icing queue status (if applicable)\n"
            "5. Ground operations capability assessment\n"
            "6. Recommendation: can the airport safely support the operation?"
        ),
        agent=runway_agent,
        context=[weather_task, flight_task],
    )
