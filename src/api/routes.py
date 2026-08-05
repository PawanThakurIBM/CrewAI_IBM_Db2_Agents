"""
API routes — REST + Server-Sent Events streaming endpoint.

POST /api/v1/analyze          → standard JSON response (blocking)
GET  /api/v1/analyze/stream   → SSE stream: fires events as each agent completes
GET  /api/v1/health           → health check
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from src.api.schemas import AgentEvent, DelayRequest, DelayResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# ── Task metadata mirrored from airline_crew.py ──────────────────────────────
_TASK_META = [
    (1, "WeatherTask",      "Aviation Meteorologist",              "Real-time weather, METAR + TAF assessment for DEL and LHR"),
    (2, "FlightTask",       "Flight Operations Specialist",        "Live flight status, delay reason, tail number, alternatives"),
    (3, "PassengerTask",    "Passenger Services Manager",          "Full manifest: VIPs, special assistance, at-risk connections"),
    (4, "RunwayTask",       "Airport Ground Operations Specialist", "Runway availability, NOTAMs, de-icing, gate status"),
    (5, "AircraftTask",     "Aircraft Fleet Coordinator",          "Airworthiness, MEL items, fuel state, rotation cascade"),
    (6, "RebookingTask",    "Airline Rebooking Specialist",        "Seat inventory, priority rebooking plan, partner endorsements"),
    (7, "DecisionTask",     "Crisis Decision Coordinator",         "Synthesise all inputs → DELAY / DIVERT / CANCEL / PROCEED"),
    (8, "CompensationTask", "Passenger Compensation Analyst",      "EU261/DGCA entitlements, vouchers, hotel, cash compensation"),
    (9, "ReviewTask",       "QA and Compliance Reviewer",          "Final policy check, risk review → approved operational brief"),
]


# ── Standard blocking endpoint ────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=DelayResponse,
    summary="Analyze a flight delay situation (blocking)",
)
async def analyze_delay(request: DelayRequest) -> DelayResponse:
    logger.info("analyze_endpoint_called", query=request.query)
    start = time.time()
    try:
        from src.crew.airline_crew import run as crew_run
        response = await asyncio.get_event_loop().run_in_executor(
            None, crew_run, request.query
        )
        elapsed = round(time.time() - start, 2)
        logger.info("analyze_endpoint_success", elapsed_seconds=elapsed)
        return DelayResponse(query=request.query, response=response, elapsed_seconds=elapsed)
    except Exception as exc:
        logger.error("analyze_endpoint_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Crew execution failed: {exc}") from exc


# ── SSE streaming endpoint ────────────────────────────────────────────────────

def _sep(char: str = "-", width: int = 72) -> None:
    print(char * width, flush=True)


def _section(title: str) -> None:
    _sep("=")
    print(f"  {title}", flush=True)
    _sep("=")


def _run_crew_with_events(query: str, event_queue: queue.Queue) -> None:
    """
    Run the full crew in a background thread.
    - verbose=True on Crew → CrewAI prints its Rich agent boxes to stdout in real time
    - Each task callback also prints a clean completion line AND pushes an SSE event
    """
    import time as _time
    from src.tasks.weather_task import make_weather_task
    from src.tasks.flight_task import make_flight_task
    from src.tasks.passenger_task import make_passenger_task
    from src.tasks.runway_task import make_runway_task
    from src.tasks.aircraft_task import make_aircraft_task
    from src.tasks.rebooking_task import make_rebooking_task
    from src.tasks.decision_task import make_decision_task
    from src.tasks.compensation_task import make_compensation_task
    from src.tasks.review_task import make_review_task
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
    from crewai import Crew, Process

    wall_start = _time.time()
    step_starts: dict[int, float] = {}

    # ── Print header + execution plan to terminal ────────────────────────────
    _section("AIRLINE DELAY MANAGEMENT ASSISTANT")
    print(f"  Query : {query}", flush=True)
    _sep()
    print(flush=True)
    print("  EXECUTION PLAN", flush=True)
    _sep()
    _ctx_map = {
        4: "context: weather, flight",
        5: "context: weather, flight",
        6: "context: passenger, flight",
        7: "context: weather, flight, passenger, runway, aircraft, rebooking",
        8: "context: decision, passenger",
        9: "context: decision, compensation",
    }
    for num, task_name, agent_name, description in _TASK_META:
        ctx = f"  [{_ctx_map[num]}]" if num in _ctx_map else ""
        print(f"  Task {num:02d}  {task_name:<20}  {agent_name:<38}  {description}{ctx}", flush=True)
    _sep()
    print(flush=True)
    print("  AGENT EXECUTION LOG", flush=True)
    _sep()

    def _make_cb(step: int, task_name: str, agent_name: str, description: str):
        step_starts[step] = _time.time()

        def _cb(output):
            elapsed = round(_time.time() - step_starts.get(step, _time.time()), 1)
            output_text = str(output.raw) if hasattr(output, "raw") else str(output)

            # ── Clean completion line in terminal (appears after Rich box) ──
            logger.info(
                "task.completed",
                step=f"{step:02d}/09",
                task=task_name,
                agent=agent_name,
                elapsed_s=elapsed,
            )

            # ── SSE event for the web UI ─────────────────────────────────
            event_queue.put(AgentEvent(
                event="agent_done",
                step=step,
                total=9,
                agent=agent_name,
                task=task_name,
                description=description,
                output=output_text,
                elapsed_s=elapsed,
            ))
        return _cb

    try:
        for step, task_name, agent_name, description in _TASK_META:
            step_starts[step] = _time.time()

        # Build tasks
        t_weather      = make_weather_task(query)
        t_flight       = make_flight_task(query)
        t_passenger    = make_passenger_task(query)
        t_runway       = make_runway_task(t_weather, t_flight)
        t_aircraft     = make_aircraft_task(t_weather, t_flight)
        t_rebooking    = make_rebooking_task(t_passenger, t_flight)
        t_decision     = make_decision_task(t_weather, t_flight, t_passenger, t_runway, t_aircraft, t_rebooking)
        t_compensation = make_compensation_task(t_decision, t_passenger)
        t_review       = make_review_task(t_decision, t_compensation)

        for task_obj, (step, task_name, agent_name, description) in zip(
            [t_weather, t_flight, t_passenger, t_runway, t_aircraft,
             t_rebooking, t_decision, t_compensation, t_review],
            _TASK_META,
        ):
            task_obj.callback = _make_cb(step, task_name, agent_name, description)

        crew = Crew(
            agents=[operations_manager, weather_agent, flight_agent, passenger_agent,
                    runway_agent, aircraft_agent, rebooking_agent,
                    decision_agent, compensation_agent, review_agent],
            tasks=[t_weather, t_flight, t_passenger, t_runway, t_aircraft,
                   t_rebooking, t_decision, t_compensation, t_review],
            process=Process.sequential,
            verbose=True,   # ← enables Rich agent boxes in terminal
        )

        result = crew.kickoff()
        final_text = str(result.raw) if hasattr(result, "raw") else str(result)

        # ── Final terminal block ─────────────────────────────────────────────
        _sep()
        wall_elapsed = round(_time.time() - wall_start, 1)
        logger.info(
            "crew.run_completed",
            total_elapsed_seconds=wall_elapsed,
            tasks_executed=9,
            agents_used=10,
        )
        print(flush=True)
        _section("FINAL RESPONSE")
        print(final_text, flush=True)
        print(flush=True)
        _sep("=")
        print(f"  Run complete.  Total time: {wall_elapsed}s", flush=True)
        _sep("=")

        event_queue.put(AgentEvent(event="final", output=final_text))

    except Exception as exc:
        logger.error("sse_crew_error", error=str(exc))
        event_queue.put(AgentEvent(event="error", message=str(exc)))
    finally:
        event_queue.put(None)  # sentinel — tells generator to stop


@router.get(
    "/analyze/stream",
    summary="Analyze a flight delay situation (SSE streaming)",
    description="Pass ?query=... as a URL parameter. Streams agent events as Server-Sent Events.",
)
async def analyze_stream(query: str, request: Request):
    logger.info("sse_endpoint_called", query=query[:80])
    event_q: queue.Queue = queue.Queue()

    # Run crew in background thread — doesn't block the event loop
    thread = threading.Thread(
        target=_run_crew_with_events,
        args=(query, event_q),
        daemon=True,
    )
    thread.start()

    async def _generator() -> AsyncGenerator[dict, None]:
        loop = asyncio.get_event_loop()
        while True:
            if await request.is_disconnected():
                break
            try:
                item = await loop.run_in_executor(None, event_q.get, True, 1.0)
            except queue.Empty:
                # Keep-alive ping
                yield {"event": "ping", "data": "{}"}
                continue

            if item is None:
                break

            yield {"event": item.event, "data": item.model_dump_json()}

    return EventSourceResponse(_generator())


# ── Health check ──────────────────────────────────────────────────────────────

@router.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok", "service": "Airline Delay Management Assistant", "version": "1.0.0"}
