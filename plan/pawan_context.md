# Pawan's Context — Airline Delay Management Assistant

Hi Pawan! Welcome to the project.

This document is your single source of truth. Read it fully before looking at any code.

---

## What Are We Building?

A **production-grade multi-agent AI system** called the **Airline Delay Management Assistant**.

The system uses **CrewAI** to orchestrate 10 specialized AI agents that collaborate to handle airline flight delays. When a user reports a delayed flight, instead of one AI answering, 10 agents work together — each solving one piece of the problem — and produce a consolidated operational response.

**Example user request:**
```
Flight AI302 from Delhi to London is delayed because of heavy rain. What should we do?
```

The system automatically coordinates weather analysis, flight status checks, passenger handling, rebooking, compensation calculation, and a final reviewed decision — all through connected agents.

---

## Current State — What's Already Built

The project is **fully implemented and running end-to-end**. Below is the status split by owner.

### Dhruv has already built:
- ✅ All 10 CrewAI agents (`src/agents/`)
- ✅ All 9 CrewAI tasks with dependency chains (`src/tasks/`)
- ✅ Crew orchestration (`src/crew/airline_crew.py`)
- ✅ External API tools — weather, flight, airport (`src/tools/`)
- ✅ Mock enterprise services — passenger, fleet, booking (`src/mock_services/`)
- ✅ FastAPI backend with SSE streaming (`src/api/`)
- ✅ Carbon Design System web UI (`static/index.html`)
- ✅ Configuration and logging (`src/config/`, `src/utils/`)

### You (Pawan) own — already implemented or ready for your review:
- ✅ IBM Db2 schema (2 tables — documents + vectors)
- ✅ 20 enterprise knowledge documents (`src/data/`)
- ✅ Haystack ingestion pipeline (`src/knowledge/ingestion_pipeline.py`)
- ✅ IBM Db2 Document Store (`src/knowledge/db2_document_store.py`)
- ✅ IBM Db2 Vector Store (`src/knowledge/db2_vector_store.py`)
- ✅ Haystack retrieval pipeline (`src/knowledge/retrieval_pipeline.py`)
- ✅ IBM Db2 Search Tool (`src/tools/db2_search_tool.py`) — THE integration point
- ✅ Tests for knowledge pipeline (`tests/test_knowledge/`)
- ✅ Test for search tool (`tests/test_tools/test_db2_search_tool.py`)

---

## Technology Stack

| Component       | Technology                                  |
|-----------------|---------------------------------------------|
| Orchestration   | CrewAI                                      |
| LLM             | **Ollama (local) — `granite3.3:8b`**        |
| Knowledge Store | **Haystack** + **IBM Db2** (Vector + Doc)   |
| API Backend     | FastAPI                                     |
| Language        | Python 3.11+                                |
| Embeddings      | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| Reranker        | `cross-encoder/ms-marco-MiniLM-L-6-v2`     |

---

## Architecture Overview

```
User Request (FastAPI → static/index.html)
         │
         ▼
Operations Manager Agent  ← CrewAI (Dhruv)
         │
         ├──► Weather Agent ──► weather API (OpenWeatherMap + aviationweather.gov)
         ├──► Flight Agent  ──► flight API (AviationStack + OpenSky)
         └──► Passenger Agent ──► mock PSS
                 │
         ┌───────┴────────┐
         ▼                ▼
   Runway Agent      Aircraft Agent    Rebooking Agent
   (← weather)       (← flight)        (← passenger + flight)
         │                │                 │
         └────────┬────────┘                │
                  ▼                         ▼
           Decision Agent  ──────────► Compensation Agent
                  │
                  ▼
           Review Agent
                  │
                  ▼
           Final Response (streamed via SSE)

  ─────────────────────────────────────────────────
  ALL AGENTS  ──►  IBM Db2 Search Tool  (YOUR FILE)
  ─────────────────────────────────────────────────
                  │
                  ▼
        Haystack Retrieval Pipeline
        [Query Embedder → Retriever → Reranker]
                  │
                  ▼
        IBM Db2 Vector Store + Document Store
```

Every single agent (all 10) calls your `db2_search_tool` whenever they need to look up policies, SOPs, regulations, or procedures.

---

## Your Files — What You Own

```
src/
├── tools/
│   └── db2_search_tool.py          ← THE integration point (all agents call this)
├── knowledge/
│   ├── ingestion_pipeline.py       ← Loads docs → chunks → embeds → stores in Db2
│   ├── retrieval_pipeline.py       ← embed → cosine → rerank → format string
│   ├── db2_document_store.py       ← AIRLINE_KB.DOCUMENTS
│   └── db2_vector_store.py         ← AIRLINE_KB.VECTORS (cosine similarity)
├── data/
│   ├── sops/           (5 docs)
│   ├── policies/       (5 docs)
│   ├── manuals/        (4 docs)
│   ├── regulations/    (3 docs)
│   └── faqs/           (3 docs)
scripts/
└── ingest_knowledge.py             ← CLI runner (populates Db2)
tests/
├── test_knowledge/
│   ├── test_ingestion_pipeline.py
│   ├── test_retrieval_pipeline.py
│   ├── test_db2_document_store.py
│   └── test_db2_vector_store.py
└── test_tools/
    └── test_db2_search_tool.py
```

---

## The Most Important Contract

**`db2_search_tool._run()` must always return a plain string.**

This is non-negotiable. CrewAI tools return strings — agents cannot handle lists or dicts.

### Return format:
```
[Document 1 — compensation_policy.md]
For delays exceeding 3 hours on EU routes, passengers are entitled to cash compensation...

[Document 2 — eu261_2004_regulation.md]
Article 7 specifies compensation of €250 for flights under 1500km...

[Document 3 — passenger_rights_policy.md]
Airlines must provide meals and refreshments after a delay of 2 hours or more...
```

### Rules:
- Always return a string (never raise an exception to the caller)
- If nothing found: return `"No relevant documents found for: {query}"`
- Return 3–5 documents maximum
- Each block starts with `[Document N — filename.md]`

---

## IBM Db2 Tables

| Table                    | Purpose                          |
|--------------------------|----------------------------------|
| `AIRLINE_KB.DOCUMENTS`   | Raw text chunks + metadata       |
| `AIRLINE_KB.VECTORS`     | 384-dim embeddings (all-MiniLM)  |

**Create these before running ingestion.** SQL is in `plan/setup_guide.md` Step 6.

---

## Haystack Pipeline Parameters

| Parameter        | Value                                         |
|------------------|-----------------------------------------------|
| Chunk size       | 512 tokens                                    |
| Chunk overlap    | 50 tokens                                     |
| Embedding model  | `sentence-transformers/all-MiniLM-L6-v2`      |
| Vector dimensions| 384                                           |
| Retrieval top-k  | 10 (vector search) → 5 (after rerank)         |
| Reranker         | `cross-encoder/ms-marco-MiniLM-L-6-v2`        |

**Do not change the embedding model.** Changing it invalidates all stored vectors.

---

## Environment Variables You Need

```env
DB2_HOST=
DB2_PORT=50000
DB2_DATABASE=BLUDB
DB2_USERNAME=
DB2_PASSWORD=
```

Add these to `.env` (copy from `.env.example`). Never commit real credentials.

---

## Getting Started (First-Time Setup)

```bash
# 1. Clone the repo
git clone git@github-ibm:PawanThakurIBM/CrewAI_IBM_Db2_Agents.git
cd CrewAI_IBM_Db2_Agents

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up .env
cp .env.example .env
# Fill in DB2 credentials in .env

# 5. Create Db2 schema (run SQL from plan/setup_guide.md Step 6)

# 6. Ingest knowledge documents
python scripts/ingest_knowledge.py

# 7. Start the server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# 8. Open http://127.0.0.1:8000 in your browser
```

Full detailed instructions are in `plan/setup_guide.md`.

---

## Running Your Tests

```bash
# Test knowledge pipeline
pytest tests/test_knowledge/

# Test search tool
pytest tests/test_tools/

# All tests
pytest
```

---

## What Dhruv Is Working On (For Reference)

- Agent unit tests (`tests/test_agents/`)
- API endpoint tests (`tests/test_api/`)
- Optional: `notification_tool.py` (SendGrid email alerts)

---

## Questions or Blockers

Coordinate with Dhruv on:
- Any change to `db2_search_tool._run()` return format — agents depend on this
- Any change to `.env` variable names — both sides must match
- Any change to the embedding model — requires full re-ingestion

---

## Reference Documents in `plan/`

| File                   | What's In It                                              |
|------------------------|-----------------------------------------------------------|
| `context.md`           | Full project overview and objectives                      |
| `architecture.md`      | System architecture, folder structure, work division      |
| `tasks.md`             | Full task breakdown (D1–D8 Dhruv, P1–P7 Pawan)           |
| `agents.md`            | All 10 agent specifications                               |
| `api_research.md`      | External API comparison and selection decisions           |
| `knowledge_dataset.md` | Per-document writing specs for all 20 knowledge files     |
| `project_status.md`    | Current completion checklist                              |
| `setup_guide.md`       | Step-by-step setup and run guide                          |
| `integration_guide.md` | Exact Dhruv ↔ Pawan contracts and sync points            |
