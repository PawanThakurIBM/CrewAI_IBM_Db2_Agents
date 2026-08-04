"""
Rebooking Task — build passenger reaccommodation plan.
Context: depends on passenger_task and flight_task outputs.
"""
from crewai import Task
from src.agents.rebooking_agent import rebooking_agent


def make_rebooking_task(passenger_task: Task, flight_task: Task) -> Task:
    return Task(
        description=(
            "You have received outputs from the Passenger Agent and the Flight Agent.\n\n"
            "The Passenger Agent has provided the full manifest with priority segments. "
            "The Flight Agent has listed available alternative flights.\n\n"
            "Using the Booking and Seat Inventory Tool:\n"
            "1. Search for available flights on the affected route: 'FLIGHTS:DEL,LHR'\n"
            "2. Generate the full rebooking plan: 'REBOOK:AI302,DEL,LHR'\n"
            "3. Apply the priority order from the passenger manifest: "
            "   special assistance → VIP/First/Business/Gold → at-risk connections → economy\n"
            "4. For each passenger segment, confirm which alternative flight they are allocated to\n"
            "5. Consult IBM Db2 for the rebooking policy and partner airline endorsement rules\n\n"
            "Extract flight and airport codes from the Flight Agent's output."
        ),
        expected_output=(
            "A complete rebooking plan containing:\n"
            "1. Available alternative flights with seat capacity per cabin\n"
            "2. Passenger allocation per alternative flight (segment breakdown)\n"
            "3. Special assistance passengers: confirmed flight and special service pre-arrangements\n"
            "4. Estimated rebooking completion time\n"
            "5. Staff and resources required\n"
            "6. Any passengers who cannot be reaccommodated and require further escalation\n"
            "7. Partner airline endorsements required (if applicable)"
        ),
        agent=rebooking_agent,
        context=[passenger_task, flight_task],
    )
