# AGENTS.md — Ask (Documentation) Mode

This file provides guidance to agents when working with code in this repository.

## Documentation Context — Non-Obvious

- **`plan/` is the sole source of truth** — the `src/` implementation does not yet exist. All architecture, agent specs, task chains, and API choices are documented in `plan/`.
- **`plan/agents.md`** — authoritative spec for all 10 agents: roles, goals, backstories, tool assignments, and execution order diagram.
- **`plan/tasks.md`** — work division between Dhruv (CrewAI side) and Pawan (Haystack/Db2 side). Tasks labeled D1–D8 = Dhruv, P1–P7 = Pawan.
- **`plan/api_research.md`** — documents why specific APIs were chosen and which are mocked (Booking, Fleet, PSS have no public free API — all are mocks).
- **`plan/knowledge_dataset.md`** — full spec for the 20 airline enterprise documents Pawan must write; includes exact content requirements per document.
- **`plan/pawan_context.md`** — onboarding doc for Pawan; contains the critical `db2_search_tool` return format contract between the two work streams.
- **The integration point** between the two work streams is `src/tools/db2_search_tool.py` — this file is owned by Pawan but consumed by all of Dhruv's agents.
- **`granite3.3` via Ollama** is the LLM — not an OpenAI or cloud model. The Ollama server must be running locally at `http://localhost:11434` before any agent execution.
- **Knowledge ingestion is a prerequisite** — `scripts/ingest_knowledge.py` must be run once before the crew can function. Without it, all `db2_search_tool` calls return nothing.
