"""
Airline Delay Management Crew.

Assembles all 10 agents and 9 tasks into a single CrewAI Crew.
Exposes a single run() function that accepts a flight delay query and returns
the final reviewed response.
"""
from __future__ import annotations

import time

from crewai import Crew, Process

from src.agents.operations_manager import operations_manager
from src.agents.weather_agent import weather_agent
from src.agents.flight_agent import flight_agent
from src.agents.passenger_agent import passenger_agent
from src.agents.runway_agent import runway_agent
from src.agents.aircraft_agent import aircraft_agent
from src.agents.rebooking_agent import rebooking_agent
from src.agents.decision_agent import decision_agent
from src.agents.compensation_agent import compensation_agent
from src.agents.review_agent import review_agent

from src.tasks.weather_task import make_weather_task
from src.tasks.flight_task import make_flight_task
from src.tasks.passenger_task import make_passenger_task
from src.tasks.runway_task import make_runway_task
from src.tasks.aircraft_task import make_aircraft_task
from src.tasks.rebooking_task import make_rebooking_task
from src.tasks.decision_task import make_decision_task
from src.tasks.compensation_task import make_compensation_task
from src.tasks.review_task import make_review_task

from src.utils.logger import get_logger

logger = get_logger(__name__)


def run(flight_query: str) -> str:
    """
    Run the full airline delay management workflow for the given query.

    Args:
        flight_query: Natural-language description of the flight delay situation.
                      e.g. "Flight AI302 from Delhi to London is delayed due to heavy rain.
                            What should we do?"

    Returns:
        The final reviewed and approved operational response as a string.
    """
    logger.info("crew_run_started", query=flight_query)
    start_time = time.time()

    # ── Build tasks (fresh instances per run, with correct context wiring) ──
    weather_task    = make_weather_task(flight_query)
    flight_task     = make_flight_task(flight_query)
    passenger_task  = make_passenger_task(flight_query)

    runway_task     = make_runway_task(weather_task, flight_task)
    aircraft_task   = make_aircraft_task(weather_task, flight_task)
    rebooking_task  = make_rebooking_task(passenger_task, flight_task)

    decision_task   = make_decision_task(
        weather_task, flight_task, passenger_task,
        runway_task, aircraft_task, rebooking_task,
    )
    compensation_task = make_compensation_task(decision_task, passenger_task)
    review_task       = make_review_task(decision_task, compensation_task)

    # ── Execution order follows the dependency chain ─────────────────────────
    # CrewAI sequential process executes tasks in list order.
    # context= on each task ensures upstream outputs are injected automatically.
    all_tasks = [
        weather_task,       # 1  ┐
        flight_task,        # 2  ├─ parallel-capable (no cross-dependency)
        passenger_task,     # 3  ┘
        runway_task,        # 4  ← needs weather + flight
        aircraft_task,      # 5  ← needs weather + flight
        rebooking_task,     # 6  ← needs passenger + flight
        decision_task,      # 7  ← needs all above
        compensation_task,  # 8  ← needs decision + passenger
        review_task,        # 9  ← needs decision + compensation
    ]

    crew = Crew(
        agents=[
            operations_manager,
            weather_agent,
            flight_agent,
            passenger_agent,
            runway_agent,
            aircraft_agent,
            rebooking_agent,
            decision_agent,
            compensation_agent,
            review_agent,
        ],
        tasks=all_tasks,
        process=Process.sequential,
        verbose=True,
    )

    logger.info("crew_kickoff", task_count=len(all_tasks))
    result = crew.kickoff()

    elapsed = round(time.time() - start_time, 2)
    logger.info("crew_run_completed", elapsed_seconds=elapsed)

    # CrewAI returns a CrewOutput object; convert to string
    return str(result)
