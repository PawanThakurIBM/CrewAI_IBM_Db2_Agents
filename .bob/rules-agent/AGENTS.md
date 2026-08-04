# AGENTS.md — Agent (Coding) Mode

This file provides guidance to agents when working with code in this repository.

## Critical Coding Rules

- **All tools must subclass `crewai.tools.BaseTool`** and implement `_run(self, query: str) -> str`. The return type must be `str` — CrewAI rejects non-string tool outputs.
- **Config access only via `src/config/settings.py`** (pydantic-settings). Never read `os.environ` or `os.getenv` directly anywhere in `src/`.
- **`allow_delegation` is False for 9 of 10 agents** — only `operations_manager.py` sets `allow_delegation=True`. Setting it True elsewhere breaks crew orchestration.
- **`verbose=True` is required** on every `crewai.Agent` and the `Crew` instance — the demo value is showing orchestration in logs.
- **Task `context=[]` must be explicit** — never assume a task has access to upstream data without listing it in `context`. Missing context means the agent re-queries and breaks the demo narrative.
- **`db2_search_tool` is the only Haystack entry point** — agent files must never import from `src/knowledge/` directly. Only `src/tools/db2_search_tool.py` touches the retrieval pipeline.
- **IBM Db2 Search Tool name is a fixed string**: `"IBM Db2 Enterprise Knowledge Search"` — changing it breaks agent tool-routing decisions.
- **Mock services live in `src/mock_services/`**, not in `src/tools/` — tools wrap them; don't put business logic in the tool layer.
- **Embedding and reranker models are fixed**: `sentence-transformers/all-MiniLM-L6-v2` for embeddings, `cross-encoder/ms-marco-MiniLM-L-6-v2` for reranking. Do not substitute without updating both ingestion and retrieval pipelines.
- **Log every step with structlog** imported from `src/utils/logger.py` — not Python's built-in `logging` directly.
- **Db2 credentials from `.env` only** — never hardcode. Use the exact variable names: `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USERNAME`, `DB2_PASSWORD`, `DB2_PROTOCOL`. Connection target: read from `.env` — never hardcode.
- **Test files mirror `src/` layout** under `tests/` (e.g., `tests/test_tools/` for `src/tools/`). When testing Db2-dependent code, mock the Db2 connection — do not require a live DB in unit tests.
