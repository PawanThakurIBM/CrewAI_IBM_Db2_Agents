"""
Compensation Task — calculate passenger entitlements.
Context: depends on decision_task and passenger_task.
"""
from crewai import Task
from src.agents.compensation_agent import compensation_agent


def make_compensation_task(decision_task: Task, passenger_task: Task) -> Task:
    return Task(
        description=(
            "You have received the operational decision brief from the Decision Agent "
            "and the passenger manifest from the Passenger Agent.\n\n"
            "Using the confirmed delay duration and cause from the Decision Agent's output:\n"
            "1. Determine whether the delay qualifies as an 'extraordinary circumstance' "
            "(weather, ATC, security) or a 'controllable delay' — this affects cash compensation liability\n"
            "2. Consult IBM Db2 for the airline's compensation policy, EU261/2004 regulation, "
            "and DGCA Passenger Charter\n"
            "3. Calculate entitlements for each passenger class based on delay duration:\n"
            "   - Meals and refreshments threshold (usually 2+ hours)\n"
            "   - Hotel accommodation threshold (if overnight delay)\n"
            "   - Cash compensation bands under EU261/2004\n"
            "   - Frequent flyer miles compensation option\n"
            "4. Produce a compensation matrix and actionable instructions for ground staff"
        ),
        expected_output=(
            "A structured compensation report containing:\n"
            "1. Delay classification: Extraordinary Circumstance (no cash compensation) "
            "or Controllable (cash compensation applies)\n"
            "2. Compensation matrix by passenger class and delay band:\n"
            "   - Meals/refreshments: who qualifies and voucher amount\n"
            "   - Hotel accommodation: who qualifies\n"
            "   - Cash compensation: €250 / €400 / €600 per EU261/2004 (if applicable)\n"
            "   - Miles compensation: option for frequent flyers\n"
            "3. Total estimated compensation cost\n"
            "4. Ground staff instructions: how to issue vouchers, process hotel bookings, "
            "and handle cash compensation claims\n"
            "5. Regulatory reference (EU261/2004 article, DGCA section)"
        ),
        agent=compensation_agent,
        context=[decision_task, passenger_task],
    )
