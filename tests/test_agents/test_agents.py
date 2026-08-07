"""
Unit tests for all 10 CrewAI agent instances.

Verifies agent construction, tool assignment, LLM binding,
allow_delegation, max_iter, and verbose settings.
No live LLM or Db2 connection required.
"""
from __future__ import annotations

import pytest
from crewai import Agent


# ── Import all agents ─────────────────────────────────────────────────────────

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tool_names(agent: Agent) -> list[str]:
    """Return the names of tools assigned to the agent."""
    return [t.name for t in agent.tools]


# ── Tests: LLM binding ────────────────────────────────────────────────────────

class TestLLMBinding:
    """All agents must use the shared Ollama LLM string.

    CrewAI wraps the 'ollama/<model>' string in a crewai.llm.LLM object;
    the model name is accessible via agent.llm.model.
    """

    @pytest.mark.parametrize("agent", [
        operations_manager, weather_agent, flight_agent, passenger_agent,
        runway_agent, aircraft_agent, rebooking_agent,
        decision_agent, compensation_agent, review_agent,
    ])
    def test_llm_starts_with_ollama(self, agent: Agent):
        # CrewAI wraps the string in crewai.llm.LLM; access via .model attribute
        model_str = getattr(agent.llm, "model", str(agent.llm))
        assert model_str.startswith("ollama/"), (
            f"{agent.role}: expected llm.model to start with 'ollama/', got {model_str!r}"
        )


# ── Tests: allow_delegation ───────────────────────────────────────────────────

class TestDelegation:
    """Only operations_manager may delegate; all others must not."""

    def test_operations_manager_can_delegate(self):
        assert operations_manager.allow_delegation is True

    @pytest.mark.parametrize("agent", [
        weather_agent, flight_agent, passenger_agent, runway_agent,
        aircraft_agent, rebooking_agent, decision_agent,
        compensation_agent, review_agent,
    ])
    def test_specialist_agents_cannot_delegate(self, agent: Agent):
        assert agent.allow_delegation is False, (
            f"{agent.role} must have allow_delegation=False"
        )


# ── Tests: max_iter ───────────────────────────────────────────────────────────

class TestMaxIter:
    """Every agent must cap iterations at 5 to prevent runaway LLM loops."""

    @pytest.mark.parametrize("agent", [
        operations_manager, weather_agent, flight_agent, passenger_agent,
        runway_agent, aircraft_agent, rebooking_agent,
        decision_agent, compensation_agent, review_agent,
    ])
    def test_max_iter_is_five(self, agent: Agent):
        assert agent.max_iter == 5, (
            f"{agent.role}: expected max_iter=5, got {agent.max_iter}"
        )


# ── Tests: verbose ────────────────────────────────────────────────────────────

class TestVerbose:
    """All agents must have verbose=False (custom structlog replaces CrewAI output)."""

    @pytest.mark.parametrize("agent", [
        operations_manager, weather_agent, flight_agent, passenger_agent,
        runway_agent, aircraft_agent, rebooking_agent,
        decision_agent, compensation_agent, review_agent,
    ])
    def test_verbose_is_false(self, agent: Agent):
        assert agent.verbose is False, (
            f"{agent.role}: expected verbose=False"
        )


# ── Tests: tool assignment ────────────────────────────────────────────────────

class TestToolAssignment:
    """Verify each agent has the correct tool set."""

    DB2_TOOL = "IBM Db2 Enterprise Knowledge Search"

    def test_all_agents_have_db2_search_tool(self):
        for agent in [
            operations_manager, weather_agent, flight_agent, passenger_agent,
            runway_agent, aircraft_agent, rebooking_agent,
            decision_agent, compensation_agent, review_agent,
        ]:
            assert self.DB2_TOOL in _tool_names(agent), (
                f"{agent.role} is missing the IBM Db2 search tool"
            )

    def test_operations_manager_has_only_db2_tool(self):
        names = _tool_names(operations_manager)
        assert names == [self.DB2_TOOL]

    def test_weather_agent_has_weather_and_db2_tools(self):
        names = _tool_names(weather_agent)
        assert "Weather Information Tool" in names
        assert self.DB2_TOOL in names

    def test_flight_agent_has_flight_and_db2_tools(self):
        names = _tool_names(flight_agent)
        assert "Flight Status and Alternatives Tool" in names
        assert self.DB2_TOOL in names

    def test_passenger_agent_has_passenger_service_tool(self):
        names = _tool_names(passenger_agent)
        assert self.DB2_TOOL in names
        # passenger_service_tool is from mock_services
        assert any("Passenger" in n or "passenger" in n.lower() for n in names), (
            f"passenger_agent tools: {names}"
        )

    def test_runway_agent_has_airport_and_db2_tools(self):
        names = _tool_names(runway_agent)
        assert "Airport Operations and NOTAM Tool" in names
        assert self.DB2_TOOL in names

    def test_aircraft_agent_has_fleet_tool(self):
        names = _tool_names(aircraft_agent)
        assert self.DB2_TOOL in names
        assert any("Fleet" in n or "fleet" in n.lower() or "Aircraft" in n for n in names), (
            f"aircraft_agent tools: {names}"
        )

    def test_rebooking_agent_has_booking_tool(self):
        names = _tool_names(rebooking_agent)
        assert self.DB2_TOOL in names
        assert any("Booking" in n or "booking" in n.lower() for n in names), (
            f"rebooking_agent tools: {names}"
        )

    def test_decision_agent_has_only_db2_tool(self):
        names = _tool_names(decision_agent)
        assert names == [self.DB2_TOOL]

    def test_compensation_agent_has_only_db2_tool(self):
        names = _tool_names(compensation_agent)
        assert names == [self.DB2_TOOL]

    def test_review_agent_has_only_db2_tool(self):
        names = _tool_names(review_agent)
        assert names == [self.DB2_TOOL]


# ── Tests: agent roles ────────────────────────────────────────────────────────

class TestAgentRoles:
    """Each agent must have its expected role string (agents route by role)."""

    def test_operations_manager_role(self):
        assert "Operations Manager" in operations_manager.role

    def test_weather_agent_role(self):
        assert "Meteorologist" in weather_agent.role

    def test_flight_agent_role(self):
        assert "Flight" in flight_agent.role

    def test_passenger_agent_role(self):
        assert "Passenger" in passenger_agent.role

    def test_runway_agent_role(self):
        assert "Ground" in runway_agent.role

    def test_aircraft_agent_role(self):
        assert "Fleet" in aircraft_agent.role

    def test_rebooking_agent_role(self):
        assert "Rebooking" in rebooking_agent.role

    def test_decision_agent_role(self):
        assert "Decision" in decision_agent.role or "Crisis" in decision_agent.role

    def test_compensation_agent_role(self):
        assert "Compensation" in compensation_agent.role

    def test_review_agent_role(self):
        assert "Review" in review_agent.role or "QA" in review_agent.role or "Quality" in review_agent.role
