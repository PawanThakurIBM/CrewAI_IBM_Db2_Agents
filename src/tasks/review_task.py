"""
Review Task — final QA validation of the complete response before delivery.
Context: depends on decision_task and compensation_task.
"""
from crewai import Task
from src.agents.review_agent import review_agent


def make_review_task(decision_task: Task, compensation_task: Task) -> Task:
    return Task(
        description=(
            "You are the final checkpoint before this operational response is delivered.\n\n"
            "You have received:\n"
            "- The Decision Agent's operational brief (primary decision, actions, communication)\n"
            "- The Compensation Agent's entitlement matrix\n\n"
            "Your job is to validate the complete package by:\n"
            "1. Checking the primary decision is consistent with the weather and aircraft data\n"
            "2. Verifying the rebooking plan covers all passenger segments\n"
            "3. Confirming compensation amounts are correct under EU261/2004 and DGCA\n"
            "4. Ensuring the passenger communication template is appropriate and complete\n"
            "5. Checking that all escalation flags have been addressed\n"
            "6. Consulting IBM Db2 to cross-check any policy figures cited\n\n"
            "If everything is correct, produce the APPROVED final response as a clean, "
            "consolidated operational brief. "
            "If there are issues, list them clearly — but still produce the best possible "
            "response with corrections applied inline."
        ),
        expected_output=(
            "The final approved consolidated operational response containing:\n\n"
            "## FLIGHT DELAY MANAGEMENT REPORT\n"
            "**Flight:** [number and route]\n"
            "**Decision:** [DELAY / DIVERT / CANCEL / PROCEED]\n"
            "**Delay Cause:** [reason and classification]\n\n"
            "**SITUATION SUMMARY**\n"
            "[2-3 sentence summary of what happened and why]\n\n"
            "**IMMEDIATE ACTIONS (0–1 hour)**\n"
            "[numbered list of specific actions]\n\n"
            "**REBOOKING PLAN**\n"
            "[summary of alternatives and passenger allocation]\n\n"
            "**PASSENGER COMMUNICATION**\n"
            "[announcement text ready to deliver]\n\n"
            "**COMPENSATION ENTITLEMENTS**\n"
            "[brief summary of what each class receives]\n\n"
            "**ESCALATION ITEMS**\n"
            "[any unresolved or high-risk items]\n\n"
            "**QA STATUS:** APPROVED / APPROVED WITH NOTES"
        ),
        agent=review_agent,
        context=[decision_task, compensation_task],
    )
