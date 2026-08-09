# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

Airline Delay Management Assistant — Python 3.11+, CrewAI 0.80.0, custom RAG pipeline, IBM Db2, Ollama (`granite3.3:8b`), FastAPI.

## Commands

```bash
# One-time knowledge ingestion (required before first run)
python scripts/ingest_knowledge.py           # incremental
python scripts/ingest_knowledge.py --wipe    # wipe + re-ingest

# Run CLI
python run_crew.py "Flight AI302 from Delhi to London is delayed. What should we do?"

# Run server
uvicorn src.api.main:app --reload --port 8000

# Run tests (no live Db2 needed — all mocked)
pytest
pytest tests/test_tools/test_db2_search_tool.py -v
pytest tests/test_knowledge/test_retrieval_pipeline.py::TestRetrieveFunction::test_returns_string -v
```

## Critical Non-Obvious Facts

- **`haystack-ai` is installed but never imported** — the entire ingestion and retrieval pipeline is custom Python. Zero Haystack classes are used at runtime. `grep -r "from haystack" src/` returns nothing.
- **`agent.llm` is a `crewai.llm.LLM` object**, not a string — read the model via `agent.llm.model`, not `str(agent.llm)`.
- **`WeatherTool` takes IATA codes but OWM needs city names** — `_city()` in `src/tools/weather_tool.py` maps via `IATA_TO_CITY` dict before calling OWM. Adding new airports requires updating both `IATA_TO_ICAO` and `IATA_TO_CITY`.
- **Vector similarity is Python-side brute-force** — `Db2VectorStore.similarity_search()` fetches up to `_SCAN_LIMIT=10_000` rows then ranks in Python. Db2 has no native vector function.
- **IBM Db2 DDL gotchas**: no `CREATE TABLE IF NOT EXISTS` — code checks `SYSCAT.TABLES` first. Duplicate key = `SQL0803N`. Always call `ibm_db.free_result(stmt)` after every query.
- **Db2 idle connection drop** — `CLI0108E`/`SQLSTATE=40003` is auto-recovered via `_reconnect()` in `src/knowledge/retrieval_pipeline.py`. One retry only.
- **`operations_manager` is the only agent with `allow_delegation=True`** — setting it True on any other agent breaks crew orchestration.
- **All 10 agents have `max_iter=5`** — prevents runaway LLM loops. Do not increase.
- **`verbose=False` on all agents and Crew** — SSE route (`src/api/routes.py`) is the sole exception (`verbose=True`).
- **Tool name is a fixed contract string**: `"IBM Db2 Enterprise Knowledge Search"` — agents route calls by this exact name.
- **Mock services are permanent** (`src/mock_services/`) — not stubs to replace. Booking data is keyed by route string e.g. `"DEL-LHR"`.
- **Task `context=[]` must be explicit** — missing context means the agent re-queries. See `src/tasks/decision_task.py` for the canonical multi-context example.
- **Changing `EMBEDDING_MODEL`** without `--wipe` re-ingestion produces garbage retrieval (mismatched vectors).
- **`configure_logging()` must be called once at startup** — `run_crew.py`, `src/api/main.py`, and `scripts/ingest_knowledge.py` each call it. Do not call it in library code.
- **`from __future__ import annotations`** required at the top of every new file.
- **Config only via `get_settings()`** from `src/config/settings.py` — never `os.environ` directly.
- **Log only via `get_logger(__name__)`** from `src/utils/logger.py` — never stdlib `logging`.

## Tool Input Protocols

| Tool | Input format |
|---|---|
| `WeatherTool` | `"DEL,LHR"` (two IATA codes, comma-separated) |
| `FlightTool` | `"STATUS:AI302"` or `"ALTERNATIVES:DEL,LHR"` |
| `BookingTool` | `"FLIGHTS:DEL,LHR"` or `"REBOOK:AI302,DEL,LHR"` |
| `AirportTool` | `"DEL"` (single IATA code) |
| `Db2SearchTool` | natural language query string |

## Db2 Tables

| Table | Purpose |
|---|---|
| `AIRLINE_KB.DOCUMENTS` | text chunks — `id VARCHAR(64)`, `content CLOB`, `source VARCHAR(512)` |
| `AIRLINE_KB.VECTORS` | embeddings — `doc_id VARCHAR(64)`, `embedding VARCHAR(32000)` (JSON float array) |
