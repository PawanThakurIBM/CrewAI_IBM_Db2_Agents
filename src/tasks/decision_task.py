"""
Decision Task — synthesise all upstream outputs into best-course-of-action.
Context: depends on ALL upstream tasks.
"""
from crewai import Task
from src.agents.decision_agent import decision_agent


def make_decision_task(
    weather_task: Task,
    flight_task: Task,
    passenger_task: Task,
    runway_task: Task,
    aircraft_task: Task,
    rebooking_task: Task,
) -> Task:
    return Task(
        description=(
            "You have received structured outputs from all specialist agents:\n"
            "- Weather Agent: severity classification and forecast\n"
            "- Flight Agent: current status, delay duration, aircraft tail, alternatives\n"
            "- Passenger Agent: manifest, priority segments, special assistance\n"
            "- Runway Agent: airport/runway status and NOTAMs\n"
            "- Aircraft Agent: airworthiness, MEL status, rotation impact\n"
            "- Rebooking Agent: reaccommodation plan and alternative flights\n\n"
            "Synthesise ALL of these inputs into a single authoritative decision. "
            "Consult IBM Db2 for relevant SOPs to validate your recommendation.\n\n"
            "Your primary decision must be one of: DELAY | DIVERT | CANCEL | PROCEED\n\n"
            "Structure your output as a formal operational brief that the Compensation Agent "
            "and Review Agent will use directly."
        ),
        expected_output=(
            "A structured operational decision brief containing:\n"
            "1. SITUATION SUMMARY: flight, route, delay cause, duration\n"
            "2. PRIMARY DECISION: DELAY / DIVERT / CANCEL / PROCEED with justification\n"
            "3. IMMEDIATE ACTIONS (0–1 hour): specific steps for ground staff, gate agents, "
            "crew, and operations control\n"
            "4. MEDIUM-TERM ACTIONS (1–6 hours): recovery plan including rebooking execution, "
            "catering, fuel, aircraft positioning\n"
            "5. PASSENGER COMMUNICATION: template announcement and key messages\n"
            "6. ESCALATION FLAGS: any safety, regulatory, or VIP issues requiring senior management\n"
            "7. DECISION RATIONALE: brief summary of how each agent's input influenced the decision"
        ),
        agent=decision_agent,
        context=[weather_task, flight_task, passenger_task, runway_task, aircraft_task, rebooking_task],
    )
