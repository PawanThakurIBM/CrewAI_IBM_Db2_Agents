# AGENTS.md — Ask (Documentation) Mode

This file provides guidance to agents when working with code in this repository.

## Documentation Context — Non-Obvious

- **The codebase is fully implemented** — ignore any prior docs saying `src/` doesn't exist. All 10 agents, 9 tasks, 4 tools, 3 mock services, knowledge pipeline, and FastAPI backend are live.
- **Two entry points**: `run_crew.py` (CLI, blocking) and `uvicorn src.api.main:app` (FastAPI with both blocking POST and SSE streaming GET endpoints at `/api/v1/analyze`).
- **`plan/` is now historical context** — for current implementation truth, read `src/`. The plan docs are useful for understanding design intent but may not match the code exactly.
- **`granite3.3:8b` via Ollama** — the model string in code is `"ollama/granite3.3:8b"` (with `:8b` tag). Ollama must be running at `http://localhost:11434` before any crew execution.
- **Logging is custom-silenced**: `src/utils/logger.py` wraps `sys.stdout` to suppress noisy CrewAI/LLM provider lines. It also silences `crewai`, `litellm`, `httpx`, `sentence_transformers`, and related loggers. Set `LOG_COLOR=true` to enable coloured output.
- **Vector similarity is NOT in Db2** — cosine similarity runs in Python after fetching up to 10,000 rows from Db2. This is intentional (Db2 LUW editions lack a native vector function).
- **Two Db2 tables, two stores**: `AIRLINE_KB.DOCUMENTS` (text chunks, CLOB) and `AIRLINE_KB.VECTORS` (JSON-serialised float arrays, VARCHAR(32000)). Both are custom Haystack store implementations — not standard Haystack components.
- **SSE streaming** (`GET /api/v1/analyze/stream?query=...`) runs the crew in a `threading.Thread` and streams `AgentEvent` payloads. The web UI in `static/` consumes these events.
- **`db2_search_tool` returns a no-results message** (not empty string) when Db2 has no matching documents — the message includes a hint to run ingestion. Agents receiving this message should not treat it as an error.
- **Knowledge ingestion is idempotent**: stable chunk IDs (`sha256[:32]`) mean re-running without `--wipe` safely skips existing documents.
- **`src/agents/_llm.py`** is the single source of truth for the LLM identifier — it is imported by all 10 agent modules.
