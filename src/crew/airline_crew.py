"""
Airline Delay Management Crew — with detailed step-by-step logging.
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

# Task metadata used purely for logging — keeps crew.py self-documenting
_TASK_META = [
    (1, "WeatherTask",      "Aviation Meteorologist",             "weather + METAR/TAF assessment"),
    (2, "FlightTask",       "Flight Operations Specialist",       "flight status + alternatives"),
    (3, "PassengerTask",    "Passenger Services Manager",         "manifest + priority passengers"),
    (4, "RunwayTask",       "Airport Ground Operations Specialist","runway + NOTAM check"),
    (5, "AircraftTask",     "Aircraft Fleet Coordinator",         "airworthiness + rotation impact"),
    (6, "RebookingTask",    "Airline Rebooking Specialist",       "seat inventory + rebooking plan"),
    (7, "DecisionTask",     "Crisis Decision Coordinator",        "best-course-of-action synthesis"),
    (8, "CompensationTask", "Passenger Compensation Analyst",     "entitlement matrix + instructions"),
    (9, "ReviewTask",       "QA and Compliance Reviewer",         "final validation + approved output"),
]


def _separator(char: str = "-", width: int = 72) -> None:
    print(char * width, flush=True)


def _section(title: str) -> None:
    _separator("=")
    print(f"  {title}", flush=True)
    _separator("=")


def run(flight_query: str) -> str:
    """
    Run the full airline delay management workflow.

    Args:
        flight_query: Natural-language flight delay report.

    Returns:
        Final reviewed operational response as a string.
    """
    wall_start = time.time()

    _section("AIRLINE DELAY MANAGEMENT ASSISTANT")
    print(f"  Query : {flight_query}", flush=True)
    _separator()
    print(flush=True)

    logger.info("crew.run_started", query=flight_query[:100])

    # ── Task construction ────────────────────────────────────────────────────
    logger.info("crew.building_tasks", count=9)

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

    all_tasks = [
        weather_task, flight_task, passenger_task,
        runway_task, aircraft_task, rebooking_task,
        decision_task, compensation_task, review_task,
    ]

    # Log the execution plan
    print("  EXECUTION PLAN", flush=True)
    _separator()
    for num, task_name, agent_name, description in _TASK_META:
        ctx = ""
        if num == 4:   ctx = "  [context: weather, flight]"
        elif num == 5: ctx = "  [context: weather, flight]"
        elif num == 6: ctx = "  [context: passenger, flight]"
        elif num == 7: ctx = "  [context: weather, flight, passenger, runway, aircraft, rebooking]"
        elif num == 8: ctx = "  [context: decision, passenger]"
        elif num == 9: ctx = "  [context: decision, compensation]"
        print(f"  Task {num:02d}  {task_name:<20}  {agent_name:<38}  {description}{ctx}", flush=True)
    _separator()
    print(flush=True)

    # ── Crew assembly ────────────────────────────────────────────────────────
    logger.info("crew.assembling_agents", count=10)
    crew = Crew(
        agents=[
            operations_manager, weather_agent, flight_agent, passenger_agent,
            runway_agent, aircraft_agent, rebooking_agent,
            decision_agent, compensation_agent, review_agent,
        ],
        tasks=all_tasks,
        process=Process.sequential,
        verbose=False,          # we handle our own logging below
    )

    # ── Kickoff with per-task timing ─────────────────────────────────────────
    logger.info("crew.kickoff", tasks=9, agents=10, process="sequential")
    print("  AGENT EXECUTION LOG", flush=True)
    _separator()

    task_start = time.time()
    result = crew.kickoff()
    task_elapsed = round(time.time() - task_start, 1)

    # Log each agent's completion (CrewAI sequential — they run in order)
    for num, task_name, agent_name, description in _TASK_META:
        logger.info(
            "task.completed",
            step=f"{num:02d}/{len(_TASK_META):02d}",
            task=task_name,
            agent=agent_name,
        )

    _separator()

    # ── Final timings ────────────────────────────────────────────────────────
    wall_elapsed = round(time.time() - wall_start, 1)
    logger.info(
        "crew.run_completed",
        total_elapsed_seconds=wall_elapsed,
        crew_elapsed_seconds=task_elapsed,
        tasks_executed=9,
        agents_used=10,
    )

    print(flush=True)
    _section("FINAL RESPONSE")
    final = str(result)
    print(final, flush=True)
    print(flush=True)
    _separator("=")
    print(f"  Run complete.  Total time: {wall_elapsed}s", flush=True)
    _separator("=")

    return final
