# AGENTS.md — Plan Mode

This file provides guidance to agents when working with code in this repository.

## Architectural Constraints — Non-Obvious

- **Crew process is `Process.sequential` with explicit `context=[]` DAG** — not hierarchical. Tasks 1–3 (Weather, Flight, Passenger) run independently; Tasks 4–6 (Runway, Aircraft, Rebooking) depend on pairs from 1–3; Task 7 (Decision) depends on all six; Tasks 8–9 depend on Decision. Reversing or parallelising the Decision → Compensation chain breaks output.
- **Vector search is Python-side brute-force**: `Db2VectorStore.similarity_search()` fetches up to `_SCAN_LIMIT=10_000` rows then does in-memory cosine ranking. This is the ceiling for knowledge base scale — beyond ~10k chunks, a dedicated vector DB is needed.
- **Two physically separate Db2 tables** (`AIRLINE_KB.DOCUMENTS` for text, `AIRLINE_KB.VECTORS` for embeddings) joined by `doc_id`. They are not interchangeable and must stay in sync — ingestion writes both atomically per chunk.
- **Reranking is two-stage**: top-10 from vector similarity → reranked to top-5 by cross-encoder. Changing `retrieval_top_k` without also adjusting the reranker call count produces inconsistent results.
- **No session/state between crew runs** — `airline_crew.run()` creates a fresh `Crew` instance per call. Task-level callbacks (`_make_callback`) use a module-level `_step_starts` dict for timing — this is the only shared state.
- **FastAPI endpoint is synchronous-by-design** — `POST /api/v1/analyze` wraps `crew.run()` in `run_in_executor` (thread pool). The SSE endpoint (`GET /api/v1/analyze/stream`) uses a dedicated `threading.Thread` + `queue.Queue` to bridge sync CrewAI to async FastAPI.
- **Ingestion must use the same embedding model as retrieval** — changing `EMBEDDING_MODEL` in `.env` without `--wipe` re-ingestion will produce mismatched vectors and garbage retrieval results.
- **IBM Db2 DDL is forward-only** — there is no migration system. Schema changes require manual DDL or `--wipe` re-ingestion. The `VECTORS.embedding` column is `VARCHAR(32000)` (JSON array string) — changing vector dimensionality requires a column rebuild.
- **Mock services contain deterministic, domain-accurate data** keyed by route (e.g., `"DEL-LHR"`). They are the permanent solution — design any enhancements as extensions to `src/mock_services/`, not replacements.
- **`src/utils/logger.py` patches `sys.stdout`** at startup to suppress CrewAI's direct `print()` noise. Any new background threads that bypass the logging system will not be filtered — pipe their output through `get_logger()`.
- **Tool input format is enforced at the tool level** — agents that produce malformed input (e.g., missing `STATUS:` prefix) get an error string back and must retry. The LLM learns this from tool descriptions; keep descriptions exact.
