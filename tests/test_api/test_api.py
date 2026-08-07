"""
Unit tests for FastAPI endpoints.

Covers:
  GET  /api/v1/health
  POST /api/v1/analyze   (blocking — mocks crew execution)
  GET  /api/v1/analyze/stream  (SSE — smoke-tests generator startup)

No live Db2, LLM, or Ollama connection required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app, raise_server_exceptions=True)


# ── Health check ──────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_status_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.json()["status"] == "ok"

    def test_health_contains_service_name(self):
        resp = client.get("/api/v1/health")
        assert "service" in resp.json()

    def test_health_contains_version(self):
        resp = client.get("/api/v1/health")
        assert "version" in resp.json()


# ── POST /api/v1/analyze ──────────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    """Blocking JSON endpoint — crew execution is mocked."""

    _QUERY = "Flight AI302 from Delhi to London is delayed due to fog. What should we do?"
    _CREW_RESPONSE = "Delay decision: DELAY 3 hours. Compensation: meal vouchers for all passengers."

    def _mock_crew_run(self, return_value: str = _CREW_RESPONSE):
        """Patch src.crew.airline_crew.run to return a canned response instantly."""
        return patch("src.crew.airline_crew.run", return_value=return_value)

    def test_analyze_returns_200(self):
        with self._mock_crew_run():
            resp = client.post("/api/v1/analyze", json={"query": self._QUERY})
        assert resp.status_code == 200

    def test_analyze_response_contains_query(self):
        with self._mock_crew_run():
            resp = client.post("/api/v1/analyze", json={"query": self._QUERY})
        assert resp.json()["query"] == self._QUERY

    def test_analyze_response_contains_response_text(self):
        with self._mock_crew_run():
            resp = client.post("/api/v1/analyze", json={"query": self._QUERY})
        assert resp.json()["response"] == self._CREW_RESPONSE

    def test_analyze_response_contains_elapsed_seconds(self):
        with self._mock_crew_run():
            resp = client.post("/api/v1/analyze", json={"query": self._QUERY})
        data = resp.json()
        assert "elapsed_seconds" in data
        assert isinstance(data["elapsed_seconds"], float)

    def test_analyze_rejects_short_query(self):
        """DelayRequest.query has min_length=10 — too-short queries must fail."""
        resp = client.post("/api/v1/analyze", json={"query": "delay"})
        assert resp.status_code == 422

    def test_analyze_rejects_missing_query(self):
        resp = client.post("/api/v1/analyze", json={})
        assert resp.status_code == 422

    def test_analyze_returns_500_on_crew_exception(self):
        with patch("src.crew.airline_crew.run", side_effect=RuntimeError("LLM unreachable")):
            resp = client.post("/api/v1/analyze", json={"query": self._QUERY})
        assert resp.status_code == 500

    def test_analyze_500_detail_contains_error(self):
        with patch("src.crew.airline_crew.run", side_effect=RuntimeError("LLM unreachable")):
            resp = client.post("/api/v1/analyze", json={"query": self._QUERY})
        assert "LLM unreachable" in resp.json()["detail"]


# ── GET /api/v1/analyze/stream ────────────────────────────────────────────────

class TestAnalyzeStreamEndpoint:
    """SSE endpoint smoke tests — verify startup behaviour without running the full crew."""

    _QUERY = "Flight AI302 from Delhi to London is delayed. What should we do?"

    def test_stream_returns_200(self):
        """
        The SSE endpoint starts a background thread and immediately begins streaming.
        We terminate after reading just the first chunk so the test is fast.
        """
        def _instant_sentinel(query: str, event_queue) -> None:
            """Immediately push the terminal sentinel so the generator exits."""
            event_queue.put(None)

        with patch("src.api.routes._run_crew_with_events", side_effect=_instant_sentinel):
            with client.stream("GET", f"/api/v1/analyze/stream?query={self._QUERY}") as resp:
                assert resp.status_code == 200

    def test_stream_content_type_is_text_event_stream(self):
        def _instant_sentinel(query: str, event_queue) -> None:
            event_queue.put(None)

        with patch("src.api.routes._run_crew_with_events", side_effect=_instant_sentinel):
            with client.stream("GET", f"/api/v1/analyze/stream?query={self._QUERY}") as resp:
                ct = resp.headers.get("content-type", "")
                assert "text/event-stream" in ct

    def test_stream_requires_query_param(self):
        """Missing query param must return 422."""
        resp = client.get("/api/v1/analyze/stream")
        assert resp.status_code == 422


# ── Schema validation ─────────────────────────────────────────────────────────

class TestSchemas:
    """Verify Pydantic schema round-trips work as expected."""

    def test_delay_request_accepts_valid_query(self):
        from src.api.schemas import DelayRequest
        req = DelayRequest(query="Flight AI302 from Delhi to London is delayed due to fog.")
        assert req.query.startswith("Flight")

    def test_delay_response_fields(self):
        from src.api.schemas import DelayResponse
        resp = DelayResponse(
            query="some query text here",
            response="operational brief text",
            elapsed_seconds=42.5,
        )
        assert resp.elapsed_seconds == 42.5

    def test_agent_event_defaults(self):
        from src.api.schemas import AgentEvent
        evt = AgentEvent(event="ping")
        assert evt.step == 0
        assert evt.total == 9
        assert evt.output == ""

    def test_agent_event_done(self):
        from src.api.schemas import AgentEvent
        evt = AgentEvent(
            event="agent_done",
            step=3,
            total=9,
            agent="Aviation Meteorologist",
            task="WeatherTask",
            description="Weather assessment",
            output="Low severity conditions at DEL and LHR.",
            elapsed_s=12.3,
        )
        assert evt.step == 3
        assert evt.agent == "Aviation Meteorologist"
        assert evt.elapsed_s == 12.3

    def test_agent_event_model_dump_json(self):
        """model_dump_json() must produce valid JSON — SSE serialisation depends on this."""
        from src.api.schemas import AgentEvent
        import json
        evt = AgentEvent(event="final", output="Final operational brief.")
        serialised = evt.model_dump_json()
        data = json.loads(serialised)
        assert data["event"] == "final"
        assert data["output"] == "Final operational brief."
