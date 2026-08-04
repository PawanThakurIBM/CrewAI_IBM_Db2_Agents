# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

Airline Delay Management Assistant — Python 3.11+, CrewAI orchestration, Haystack + IBM Db2 knowledge pipeline, Ollama LLM (`granite3.3` at `http://localhost:11434`), FastAPI backend. **The codebase does not yet exist** — all `src/`, `tests/`, `scripts/` structure is planned in `plan/` but not yet implemented.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
uvicorn src.api.main:app --reload

# One-time knowledge ingestion (must run before first use)
python scripts/ingest_knowledge.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_tools/test_db2_search_tool.py

# Run a single test by name
pytest tests/test_tools/test_db2_search_tool.py::test_name -v
```

## Architecture — Non-Obvious

- **All 10 agents share one tool**: `db2_search_tool` (in `src/tools/db2_search_tool.py`) is given to every agent. It is the only path into IBM Db2 — agents never call Haystack directly.
- **Task context chain is explicit**: CrewAI tasks declare `context=[upstream_task]` — downstream agents receive prior agent outputs automatically. Do not re-query data already fetched upstream.
- **Decision Agent feeds Compensation Agent**: `decision_task` must be in the `context` list of `compensation_task`. The order matters — Compensation Agent runs after Decision Agent, not in parallel.
- **`db2_search_tool._run()` must return a plain string**: CrewAI tools require string return values. Never return a list or dict — format results as text inside `_run()`.
- **Operations Manager is the only agent with `allow_delegation=True`**: all other 9 agents have `allow_delegation=False`.
- **Two separate mock services vs. real APIs**: Passenger (PSS), Fleet, and Booking have no public free APIs — use mocks in `src/mock_services/`. Weather (OpenWeatherMap + aviationweather.gov) and Flight (AviationStack) use real APIs.

## IBM Db2 Search Tool Contract

`name = "IBM Db2 Enterprise Knowledge Search"` (exact string — agents use this to route calls).

Return format (agents depend on this layout):
```
[Document 1 — filename.md]
<text content>

[Document 2 — filename.md]
<text content>
```

## Haystack Pipeline Parameters

| Parameter | Value |
|-----------|-------|
| Chunk size | 512 tokens, 50 token overlap |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Retrieval top-k | 10 (then reranked to top 5) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |

## Environment Variables

```env
# IBM Db2
DB2_HOST=<your-db2-hostname>
DB2_PORT=50000
DB2_DATABASE=CREWAI
DB2_USERNAME=pawan
DB2_PASSWORD=<your-db2-password>
DB2_PROTOCOL=TCPIP

# External APIs
OPENWEATHER_API_KEY=
AVIATIONSTACK_API_KEY=
SENDGRID_API_KEY=       # optional, notification only
```
`aviationweather.gov` and OpenSky Network require **no API key**.

## Code Style

- Python type hints on all function signatures
- `pydantic-settings` for config in `src/config/settings.py` (never read `os.environ` directly)
- Structured logging via `structlog` — every agent execution, tool call, and API call must be logged
- `crewai.tools.BaseTool` subclass for all tools (not plain functions)
- `verbose=True` on all agents and the Crew instance (required to show orchestration in demo)

## Knowledge Dataset

20 `.md` documents under `src/data/{sops,policies,manuals,regulations,faqs}/` — full spec in [`plan/knowledge_dataset.md`](plan/knowledge_dataset.md). Must be ingested before running the crew.
