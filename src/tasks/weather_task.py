"""
Weather Task — assess meteorological conditions for the delayed flight route.
Context: receives the raw user request (flight + delay reason).
"""
from crewai import Task
from src.agents.weather_agent import weather_agent


def make_weather_task(flight_query: str) -> Task:
    return Task(
        description=(
            f"You have received the following flight delay report:\n\n"
            f"{flight_query}\n\n"
            "Using the Weather Information Tool, retrieve current weather conditions, "
            "METAR, and TAF for both the departure and arrival airports mentioned in the report. "
            "Also check the 24-hour forecast. "
            "Then consult the IBM Db2 Enterprise Knowledge Search for the airline's weather "
            "operations SOP to classify the severity and operational impact. "
            "Identify the IATA codes of departure and arrival airports from the flight report "
            "(e.g., DEL for Delhi, LHR for London Heathrow). "
            "Provide a complete structured weather assessment."
        ),
        expected_output=(
            "A structured weather assessment report containing:\n"
            "1. Departure airport: current conditions, wind speed, visibility, METAR, TAF\n"
            "2. Arrival airport: current conditions, wind speed, visibility, METAR, TAF\n"
            "3. 24-hour forecast summary for both airports\n"
            "4. Severity classification: Low / Medium / High / Severe\n"
            "5. Operational impact statement: whether weather is the primary delay cause\n"
            "6. Whether conditions are improving or deteriorating\n"
            "7. Alternate airport conditions if relevant"
        ),
        agent=weather_agent,
    )
