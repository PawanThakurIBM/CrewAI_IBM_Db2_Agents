# AGENTS.md — Agent (Coding) Mode

This file provides guidance to agents when working with code in this repository.

## Critical Coding Rules

- **`haystack-ai` is used for ingestion only** — `src/knowledge/ingestion_pipeline.py` imports `haystack.Pipeline`, `MarkdownToDocument`, `SentenceTransformersDocumentEmbedder`, `DocumentWriter` etc. Retrieval (`src/knowledge/retrieval_pipeline.py`) is custom — zero Haystack imports. Do not add Haystack imports to retrieval.
- **Embedding model is `ibm-granite/granite-embedding-125m-english`** (768-dim). Changing it requires `--wipe` re-ingestion. Verify first with `scripts/test_granite_embedding.py`.
- **All tools must subclass `crewai.tools.BaseTool`** with `_run(self, query: str) -> str`. Non-string return breaks CrewAI.
- **Config only via `get_settings()`** (`src/config/settings.py`). Never `os.environ`/`os.getenv` anywhere in `src/`.
- **`allow_delegation=True` on `operations_manager` only** — all 9 others must be `False`.
- **`max_iter=5` on every agent** — do not raise. Default (25) causes runaway loops with Ollama.
- **`verbose=False` on all agents and Crew** — SSE route is the sole exception.
- **`db2_search_tool` is the only Haystack entry point** — agents never import from `src/knowledge/` directly.
- **Tool name fixed string**: `"IBM Db2 Enterprise Knowledge Search"` — do not rename.
- **Mock services in `src/mock_services/` are permanent** — not temporary stubs.
- **Log via `get_logger(__name__)`** (`src/utils/logger.py`). Never stdlib `logging` directly.
- **Db2 DDL**: no `CREATE TABLE IF NOT EXISTS` — check `SYSCAT.TABLES` first. Duplicate key = `SQL0803N`. Always `ibm_db.free_result(stmt)`.
- **`agent.llm.model`** gives the model string — `str(agent.llm)` gives the object repr, not the model name.
- **`WeatherTool`** calls OWM with city names, not IATA codes — mapping is in `IATA_TO_CITY` dict in `src/tools/weather_tool.py`. Add new airports to both `IATA_TO_ICAO` and `IATA_TO_CITY`.
- **`from __future__ import annotations`** at top of every new file.
- **Each `src/agents/<name>.py`** exports one module-level `Agent` instance. Each `src/tasks/<name>.py`** exports one `make_<name>_task(...)` factory.
- **Mock Db2 in tests** by patching `ibm_db` at module level: `patch("src.knowledge.db2_document_store.ibm_db")`. `asyncio_mode = auto` in pytest.ini — no decorator needed for async tests.
