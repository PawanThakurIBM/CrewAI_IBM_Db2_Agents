# AGENTS.md — Ask (Documentation) Mode

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Documentation Context

- **`haystack-ai==2.9.0` is in `requirements.txt` but zero Haystack classes are imported anywhere in `src/`** — the entire RAG pipeline is custom. Do not describe this as "built on Haystack". Correct description: "Haystack-inspired custom RAG pipeline".
- **Two entry points**: `run_crew.py` (CLI) and `uvicorn src.api.main:app` (FastAPI with blocking POST + SSE GET at `/api/v1/analyze`).
- **`plan/` is historical** — for current truth read `src/`. Plan docs describe intent, not implementation.
- **Logging silences CrewAI noise**: `src/utils/logger.py` patches `sys.stdout` and silences `crewai`, `litellm`, `httpx`, `sentence_transformers` loggers. Set `LOG_COLOR=true` for coloured output.
- **Vector similarity is NOT in Db2** — cosine runs in Python after fetching up to 10,000 rows. This is intentional (Db2 LUW has no native vector function).
- **`db2_search_tool` returns a human-readable no-results message** (not empty string / not exception) when Db2 has no matching docs — agents should not treat it as an error.
- **`WeatherTool` uses `IATA_TO_CITY` mapping** before calling OWM — IATA codes alone fail OWM lookup (e.g. "LHR" → "London"). METAR/TAF use `IATA_TO_ICAO` mapping to aviationweather.gov.
- **`agent.llm` is a `crewai.llm.LLM` wrapper** — the actual model string is at `agent.llm.model`.
