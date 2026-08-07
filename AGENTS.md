# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

Airline Delay Management Assistant — Python 3.11+, CrewAI 0.80.0 orchestration, Haystack + IBM Db2 knowledge pipeline, Ollama LLM (`granite3.3:8b` at `http://localhost:11434`), FastAPI backend. **The codebase is fully implemented** — `src/`, `tests/`, `scripts/` all exist.

## Commands

```bash
# Install dependencies (Python 3.11+ required; use the arm64 venv on Apple Silicon)
# One-time venv creation:
#   ~/python311-standalone/python/bin/python3.11 -m venv .venv
pip install -r requirements.txt

# One-time knowledge ingestion (REQUIRED before first crew run)
python scripts/ingest_knowledge.py              # incremental (skip existing)
python scripts/ingest_knowledge.py --wipe       # wipe and re-ingest

# Run CLI (default query if no args)
python run_crew.py
python run_crew.py "Flight AI302 from Delhi to London is delayed. What should we do?"

# Run FastAPI server (serves UI at / and API at /api/v1)
uvicorn src.api.main:app --reload --port 8000

# Run all tests (no live Db2 needed — all Db2 calls mocked)
pytest

# Run a single test file
pytest tests/test_tools/test_db2_search_tool.py -v

# Run a single test by name
pytest tests/test_knowledge/test_retrieval_pipeline.py::TestRetrieveFunction::test_returns_string -v

# Enable coloured log output
LOG_COLOR=true python run_crew.py
```

## Architecture — Non-Obvious

- **All 10 agents share one tool**: `db2_search_tool` singleton in `src/tools/db2_search_tool.py`. Agents never import from `src/knowledge/` directly.
- **LLM is resolved as a string**: `src/agents/_llm.py` builds `"ollama/granite3.3:8b"` — CrewAI v1.x wraps this in a `crewai.llm.LLM` object; access the model string via `agent.llm.model`, not `str(agent.llm)`.
- **Task context chain is explicit**: tasks declare `context=[upstream_task]` — missing context means the agent re-queries, breaking results. See `src/tasks/decision_task.py` for the canonical example.
- **Decision → Compensation ordering is non-negotiable**: `compensation_task` must have `decision_task` in context. Compensation Agent runs after Decision Agent.
- **`operations_manager` is the only agent with `allow_delegation=True`** — all 9 others are `False`. In `src/crew/airline_crew.py`, `verbose=False` on the Crew (logging is custom).
- **SSE streaming endpoint** (`GET /api/v1/analyze/stream?query=...`) runs the crew in a background thread and pushes `AgentEvent` SSE payloads. The blocking endpoint (`POST /api/v1/analyze`) uses `run_in_executor`.
- **Vector similarity is Python-side**: Db2 does not perform cosine similarity. `Db2VectorStore.similarity_search()` fetches up to `_SCAN_LIMIT=10_000` rows then ranks in Python.
- **IBM Db2 does not support `CREATE TABLE IF NOT EXISTS`** — `Db2DocumentStore` and `Db2VectorStore` check `SYSCAT.TABLES` first before running DDL.
- **Duplicate key in Db2 is SQL0803**: `write_documents()` silently skips inserts that raise an error containing `"SQL0803"`.
- **Ingestion generates stable IDs**: `_stable_id(source, chunk_index)` uses `sha256[:32]` so re-running ingestion skips existing chunks without duplicates.
- **Mock services are permanent**: `src/mock_services/` (Booking, Fleet, PSS) are not stubs to be replaced — they are the final implementations. `booking_service.py` contains deterministic flight data keyed by `"DEL-LHR"` etc.
- **Tool input protocols**: Tools parse prefixed strings — `WeatherTool` takes `"DEL,LHR"`, `FlightTool` takes `"STATUS:AI302"` or `"ALTERNATIVES:DEL,LHR"`, `BookingTool` takes `"FLIGHTS:DEL,LHR"` or `"REBOOK:AI302,DEL,LHR"`.

## IBM Db2 Search Tool Contract

`name = "IBM Db2 Enterprise Knowledge Search"` (exact string — agents use this to route calls).

Return format:
```
[Document 1 — filename.md]
<text content>

[Document 2 — filename.md]
<text content>
```

## Haystack Pipeline

| Parameter | Value |
|-----------|-------|
| Chunk size | 512 tokens, 50 token overlap (~4 chars/token estimate) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Retrieval top-k | 10 (then reranked to top 5) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Scan limit | 10,000 vectors max before Python-side cosine ranking |

## Environment Variables

```env
DB2_HOST=<your-db2-hostname>
DB2_PORT=50000
DB2_DATABASE=CREWAI
DB2_USERNAME=<your-db2-username>
DB2_PASSWORD=<see .env>
DB2_PROTOCOL=TCPIP
DB2_SCHEMA=AIRLINE_KB
OPENWEATHER_API_KEY=<see .env>
AVIATIONSTACK_API_KEY=<see .env>
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=granite3.3:8b
```
`aviationweather.gov` and OpenSky Network require **no API key**.
`DB2_SCHEMA` defaults to `AIRLINE_KB` — schema name is always uppercased in code.

## Code Style

- Python type hints on all function signatures; `from __future__ import annotations` at top of every file
- Config via `get_settings()` from `src/config/settings.py` — never `os.environ`/`os.getenv`
- Logging via `get_logger(__name__)` from `src/utils/logger.py` — never stdlib `logging` directly; `configure_logging()` called once at startup (`run_crew.py`, `src/api/main.py`, `scripts/ingest_knowledge.py`)
- All tools subclass `crewai.tools.BaseTool` with `_run(self, query: str) -> str`; singletons exported from same module (e.g. `db2_search_tool = Db2SearchTool()`)
- Agent modules export a single module-level agent instance (e.g. `weather_agent = Agent(...)`)
- Task modules export a `make_<name>_task(...)` factory function returning `crewai.Task`
- `verbose=False` on all agents and the main Crew (custom logging replaces CrewAI's built-in output); SSE endpoint uses `verbose=True` for Rich terminal boxes

## Knowledge Dataset

20 `.md` documents under `src/data/{sops,policies,manuals,regulations,faqs}/`. Must be ingested before running the crew.
