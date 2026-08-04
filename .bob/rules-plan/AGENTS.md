# AGENTS.md — Plan Mode

This file provides guidance to agents when working with code in this repository.

## Architectural Constraints — Non-Obvious

- **Crew process is sequential with explicit context** — not hierarchical. Despite parallel-looking execution (Weather/Flight/Passenger start together), CrewAI `Process.sequential` with `context=[]` dependencies achieves the DAG. Do not use `Process.hierarchical` without re-evaluating the Operations Manager delegation logic.
- **Decision Agent → Compensation Agent ordering is non-negotiable**: Compensation Agent's `context` must include `decision_task`. Reversing or parallelizing these breaks compensation calculation logic.
- **Two separate storage systems in Db2**: a document store (raw chunks + metadata) and a vector store (embeddings). Both are custom Haystack `DocumentStore` implementations in `src/knowledge/`. They are not interchangeable.
- **Reranking is a two-stage retrieval**: top-10 from vector similarity → reranked to top-5. Changing retrieval top-k without updating the reranker call count produces inconsistent results.
- **No session or state between crew runs** — agents are stateless. The crew is instantiated fresh per request in `airline_crew.run()`. Any caching must be implemented outside the agent layer.
- **FastAPI endpoint is synchronous-by-design** — `airline_crew.run()` is blocking. For production scale, this needs async handling or background task offloading (not implemented in the current plan).
- **Mock services are the permanent solution** for Booking, Fleet, and PSS — there is no plan to replace them with real APIs. Design them as realistic, typed implementations, not stubs.
- **Knowledge dataset must exist before integration testing** — the P2 task (writing 20 documents) is a hard dependency for P3–P6 and all of Dhruv's integration tests. Plan accordingly.
- **Haystack embedding model is shared** between ingestion and retrieval — changing the model requires re-running full ingestion. The two pipelines must always use the same model.
