# AGENTS.md — Agent (Coding) Mode

This file provides guidance to agents when working with code in this repository.

## Critical Coding Rules

- **All tools must subclass `crewai.tools.BaseTool`** and implement `_run(self, query: str) -> str`. The return type must be `str` — CrewAI rejects non-string tool outputs.
- **Config access only via `get_settings()` in `src/config/settings.py`** (pydantic-settings). Never read `os.environ` or `os.getenv` directly anywhere in `src/`.
- **`allow_delegation` is False for 9 of 10 agents** — only `src/agents/operations_manager.py` sets it `True`. Setting it True elsewhere breaks crew orchestration.
- **`verbose=False` on all agents and the main Crew** — custom structlog-based logging replaces CrewAI's built-in output. The SSE route (`src/api/routes.py`) is the sole exception (`verbose=True` for Rich terminal boxes).
- **Task `context=[]` must be explicit** — never assume a task has access to upstream data without listing it. See `src/tasks/decision_task.py` for the canonical multi-context example.
- **`db2_search_tool` is the only Haystack entry point** — agent files must never import from `src/knowledge/` directly. Only `src/tools/db2_search_tool.py` touches the retrieval pipeline.
- **IBM Db2 Search Tool name is a fixed string**: `"IBM Db2 Enterprise Knowledge Search"` — changing it breaks agent tool-routing.
- **Mock services live in `src/mock_services/`**, not in `src/tools/` — tools wrap them; no business logic in the tool layer. Mocks are permanent (not stubs to be replaced).
- **Embedding and reranker models are fixed** — changing either requires re-running full ingestion. Both pipelines must use the same model.
- **Log every step with structlog** via `get_logger(__name__)` from `src/utils/logger.py` — not Python's built-in `logging` directly. `configure_logging()` is called once at startup.
- **Db2 credentials from `.env` only** — never hardcode. Exact var names: `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USERNAME`, `DB2_PASSWORD`, `DB2_PROTOCOL`, `DB2_SCHEMA`.
- **Test files mirror `src/` layout** under `tests/` (e.g., `tests/test_knowledge/` for `src/knowledge/`). Mock Db2 by patching `ibm_db` at the module level (e.g., `patch("src.knowledge.db2_document_store.ibm_db")`). The `asyncio_mode = auto` pytest setting means async tests need no decorator.
- **Tool input protocols are prefix-based**: `FlightTool` → `"STATUS:AI302"` / `"ALTERNATIVES:DEL,LHR"`, `WeatherTool` → `"DEL,LHR"`, `BookingTool` → `"FLIGHTS:DEL,LHR"` / `"REBOOK:AI302,DEL,LHR"`, `AirportTool` → `"DEL"` (3-letter IATA only).
- **IBM Db2 DDL gotchas**: no `CREATE TABLE IF NOT EXISTS` — check `SYSCAT.TABLES` first. Duplicate key error code is `SQL0803N`. Always call `ibm_db.free_result(stmt)` after every query.
- **LLM is a plain string** `"ollama/<model>"` built in `src/agents/_llm.py` — CrewAI wraps it in `crewai.llm.LLM`; read the model back via `agent.llm.model`, not `str(agent.llm)`.
- **`from __future__ import annotations`** is required at the top of every new file for forward-reference type hints.
- **Agent module pattern**: each `src/agents/<name>.py` exports exactly one module-level `Agent` instance. Each `src/tasks/<name>.py` exports one `make_<name>_task(...)` factory returning `crewai.Task`.
