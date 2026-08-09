# AGENTS.md — Plan Mode

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Architectural Constraints

- **`haystack-ai` is a dead dependency** — installed but unused. Any plan to "use Haystack" requires building a proper `BaseDocumentStore` subclass first; there is no official IBM Db2 Haystack integration on PyPI.
- **Crew process is `Process.sequential` with explicit `context=[]` DAG** — Tasks 1–3 (Weather, Flight, Passenger) independent; Tasks 4–6 depend on pairs from 1–3; Task 7 (Decision) depends on all six; Tasks 8–9 depend on Task 7. Parallelising or reordering the Decision→Compensation chain breaks output.
- **Vector search is Python-side brute-force** — `_SCAN_LIMIT=10_000` rows fetched then ranked in memory. Hard ceiling for knowledge base scale. Beyond ~10k chunks a dedicated vector DB is needed.
- **Two Db2 tables joined by `doc_id`** — `AIRLINE_KB.DOCUMENTS` (text) and `AIRLINE_KB.VECTORS` (JSON float arrays in `VARCHAR(32000)`). Ingestion writes both atomically per chunk. Changing vector dimensionality requires a column rebuild — no migration system.
- **SSE endpoint bridges sync→async via `threading.Thread` + `queue.Queue`** — `POST /api/v1/analyze` uses `run_in_executor`. New background threads that bypass `get_logger()` will not be filtered by the stdout patch.
- **Changing `EMBEDDING_MODEL` without `--wipe` re-ingestion** produces mismatched vectors and garbage retrieval. Both ingestion and retrieval must use identical models.
- **Mock services contain deterministic domain data keyed by route** (e.g. `"DEL-LHR"`) — permanent solution, not placeholders. Design enhancements as extensions to `src/mock_services/`, not replacements.
- **`WeatherTool` has two separate IATA mappings**: `IATA_TO_ICAO` (for METAR/TAF via aviationweather.gov) and `IATA_TO_CITY` (for OWM current/forecast). Both must be updated when adding a new airport.
- **No session/state between crew runs** — `Crew` is instantiated fresh per call. `_step_starts` timing dict in SSE route is the only shared state and is local to each thread.
