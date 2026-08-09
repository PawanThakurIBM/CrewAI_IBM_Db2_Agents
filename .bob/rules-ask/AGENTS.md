# AGENTS.md — Ask (Documentation) Mode

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Documentation Context

- **`haystack-ai==2.9.0` is used for ingestion** — `src/knowledge/ingestion_pipeline.py` runs a real Haystack `Pipeline`. Retrieval is custom Python. Correct description: "Haystack ingestion, custom retrieval pipeline".
- **Embedding model is `ibm-granite/granite-embedding-125m-english`** (768-dim, Apache 2.0, HuggingFace). Was previously `all-MiniLM-L6-v2` (384-dim). Current Db2 vectors are 768-dim.
- **Two entry points**: `run_crew.py` (CLI) and `uvicorn src.api.main:app` (FastAPI with blocking POST + SSE GET at `/api/v1/analyze`).
- **`plan/` is historical** — for current truth read `src/`. Plan docs describe intent, not implementation.
- **Logging silences CrewAI noise**: `src/utils/logger.py` patches `sys.stdout` and silences `crewai`, `litellm`, `httpx`, `sentence_transformers` loggers. Set `LOG_COLOR=true` for coloured output.
- **Vector similarity is NOT in Db2** — cosine runs in Python after fetching up to 10,000 rows. This is intentional (Db2 LUW has no native vector function).
- **`db2_search_tool` returns a human-readable no-results message** (not empty string / not exception) when Db2 has no matching docs — agents should not treat it as an error.
- **`WeatherTool` uses `IATA_TO_CITY` mapping** before calling OWM — IATA codes alone fail OWM lookup (e.g. "LHR" → "London"). METAR/TAF use `IATA_TO_ICAO` mapping to aviationweather.gov.
- **`agent.llm` is a `crewai.llm.LLM` wrapper** — the actual model string is at `agent.llm.model`.
