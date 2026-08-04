# Pawan's Context — Airline Delay Management Assistant

Hi Pawan! Welcome to the project.

This document gives you everything you need to get started and understand your role.
Read this fully before diving into code.

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

## Technology Stack

| Component       | Technology                                |
|-----------------|-------------------------------------------|
| Orchestration   | CrewAI                                    |
| LLM             | **Ollama (local) — `granite3.3` model**   |
| Knowledge Store | **Haystack** + **IBM Db2** (Vector + Doc) |
| API Backend     | FastAPI                                   |
| Language        | Python 3.11+                              |
| Embeddings      | `sentence-transformers/all-MiniLM-L6-v2`  |
| Reranker        | `cross-encoder/ms-marco-MiniLM-L-6-v2`   |

---

## The Two Work Streams

The project is divided between **Dhruv** (CrewAI side) and **you, Pawan** (Haystack + IBM Db2 side).

### Dhruv owns:
- All 10 CrewAI agents
- All CrewAI tasks and crew orchestration
- External API tools (weather, flight, airport)
- Mock enterprise services (passenger, fleet, booking)
- FastAPI backend
- Configuration and logging

### You (Pawan) own:
- IBM Db2 setup and schema
- Enterprise knowledge dataset (20 documents)
- Haystack ingestion pipeline
- IBM Db2 Document Store integration
- IBM Db2 Vector Store integration
- Haystack retrieval pipeline (with reranker)
- IBM Db2 Search Tool (the CrewAI tool that wraps Haystack)

**The integration point** — what Dhruv's agents call and what you build — is the `IBM Db2 Search Tool` in `src/tools/db2_search_tool.py`. This is the most critical interface between the two work streams.

---

## Architecture Overview

```
User Request (FastAPI)
        │
        ▼
Operations Manager Agent  ← CrewAI (Dhruv)
        │
        ├──► Weather Agent ──► weather API
        ├──► Flight Agent  ──► flight API
        └──► Passenger Agent ──► mock PSS
                │
        ┌───────┴────────┐
        ▼                ▼
  Runway Agent      Aircraft Agent    Rebooking Agent
        │                │                 │
        └────────┬────────┘                │
                 ▼                         ▼
          Decision Agent ──────────► Compensation Agent
                 │
                 ▼
          Review Agent
                 │
                 ▼
          Final Response

          ─────────────────────────────────────────
          ALL AGENTS  ──►  IBM Db2 Search Tool (YOU)
          ─────────────────────────────────────────
                 │
                 ▼
          Haystack Retrieval Pipeline
          [Query Embedder → Retriever → Reranker → Answer Builder]
                 │
                 ▼
          IBM Db2 Vector Store + Document Store
```

Every single agent (all 10) calls your `db2_search_tool` whenever they need to look up policies, SOPs, regulations, or procedures. This is the backbone of the system.

---

## Your Tasks — Detailed

### P1 · IBM Db2 Setup

Configure IBM Db2 and create the schema needed for Haystack.

You will need two tables:
- One for **document store** (document id, content, metadata)
- One for **vector store** (document id, embedding vector, metadata)

Store credentials in `.env` (never commit real credentials).

Required env variables:
```env
DB2_HOST=
DB2_PORT=
DB2_DATABASE=
DB2_USERNAME=
DB2_PASSWORD=
```

---

### P2 · Enterprise Knowledge Dataset

Create 20 realistic airline enterprise documents under `src/data/`.

**Folder structure:**
```
src/data/
├── sops/           ← Standard Operating Procedures (5 docs)
├── policies/       ← Passenger rights, compensation, rebooking (5 docs)
├── manuals/        ← Ops manuals for crew, ground, aircraft, airport (4 docs)
├── regulations/    ← EU261/2004, DGCA, IATA delay codes (3 docs)
└── faqs/           ← Passenger FAQ, crew FAQ, ops FAQ (3 docs)
```

**Guidelines for writing documents:**
- Plain English markdown format
- 400–800 words per document
- Use realistic airline terminology (IATA codes, ICAO, MEL, FDP, NOTAM)
- Base content on publicly available IATA, EU, and DGCA guidelines — don't copy, paraphrase
- Include specific numeric thresholds (e.g., "meals after 2 hours", "€250 for flights under 1500km")
- Documents should read like real internal airline policy documents

Full document list and specs are in `plan/knowledge_dataset.md`.

---

### P3 · Haystack Ingestion Pipeline

**File:** `src/knowledge/ingestion_pipeline.py`

Steps:
1. Load all `.md` files from `src/data/` recursively
2. Clean and normalize text
3. Split into chunks: **512 tokens, 50 token overlap**
4. Generate embeddings using `sentence-transformers/all-MiniLM-L6-v2`
5. Store document chunks in IBM Db2 Document Store
6. Store embeddings in IBM Db2 Vector Store

Also create `scripts/ingest_knowledge.py` — a CLI script to run this end-to-end with progress logging.

---

### P4 · IBM Db2 Document Store + Vector Store

**Files:**
- `src/knowledge/db2_document_store.py`
- `src/knowledge/db2_vector_store.py`

These must follow Haystack's `DocumentStore` interface so the retrieval pipeline can use them.

The Document Store stores the raw text chunks and metadata.
The Vector Store stores the embedding vectors and supports cosine similarity search.

---

### P5 · Haystack Retrieval Pipeline

**File:** `src/knowledge/retrieval_pipeline.py`

Steps:
1. Accept a query string
2. Embed the query using the same model (`all-MiniLM-L6-v2`)
3. Perform cosine similarity search against IBM Db2 Vector Store (top-k=10)
4. Rerank results using `cross-encoder/ms-marco-MiniLM-L-6-v2` (return top 5)
5. Fetch full document text from Document Store
6. Return formatted list of documents

This is the pipeline that the IBM Db2 Search Tool calls.

---

### P6 · IBM Db2 Search Tool (THE INTEGRATION POINT)

**File:** `src/tools/db2_search_tool.py`

This is the most important file you will write. Dhruv's agents call this.

Requirements:
- Must subclass `crewai.tools.BaseTool`
- `name = "IBM Db2 Enterprise Knowledge Search"`
- `description` — a clear one-paragraph description that agents use to decide when to call this tool
- `_run(query: str) -> str` — calls the retrieval pipeline and formats results as readable text

Example output format:
```
[Document 1 — flight_delay_sop.md]
Passengers must be provided meals after a 2-hour delay...

[Document 2 — compensation_policy.md]
For delays exceeding 3 hours on EU routes, cash compensation of €250 applies...
```

---

### P7 · Testing

- Unit test for ingestion pipeline (with a small test document set)
- Unit test for retrieval pipeline (mocked Db2)
- Unit test for IBM Db2 Search Tool

---

## Integration Point with Dhruv

Once both sides are done:

1. You run `python scripts/ingest_knowledge.py` to populate Db2
2. Dhruv imports your `db2_search_tool` into all agent definitions
3. We run the crew end-to-end with the sample query

**Critical:** Your `db2_search_tool._run()` must return a string (not a list).
CrewAI tools must always return strings. Dhruv's agents depend on this contract.

---

## File Locations Summary — Your Files

```
src/
├── tools/
│   └── db2_search_tool.py          ← P6 (THE integration point)
├── knowledge/
│   ├── ingestion_pipeline.py       ← P3
│   ├── retrieval_pipeline.py       ← P5
│   ├── db2_document_store.py       ← P4
│   └── db2_vector_store.py         ← P4
├── data/
│   ├── sops/                       ← P2
│   ├── policies/                   ← P2
│   ├── manuals/                    ← P2
│   ├── regulations/                ← P2
│   └── faqs/                       ← P2
scripts/
└── ingest_knowledge.py             ← P3 CLI runner
tests/
└── test_knowledge/                 ← P7
```

---

## Key Dependencies (for your side)

```txt
haystack-ai
ibm-db
ibm-db-sa
sentence-transformers
torch
transformers
```

---

## Getting Started

1. Clone the repo
2. Create `.env` from `.env.example` and fill in your IBM Db2 credentials
3. Read `plan/context.md` for full project overview
4. Read `plan/architecture.md` for system design and folder structure
5. Read `plan/tasks.md` for the full task list (your tasks are labeled P1–P7)
6. Read `plan/knowledge_dataset.md` for document writing specs
7. Start with **P1** (Db2 setup) → **P2** (write the documents) → **P3–P5** (pipeline) → **P6** (search tool)

**Start with P2 (knowledge dataset) in parallel with P1** — you can write documents while Db2 is being configured.

---

## Questions or Blockers

Coordinate with Dhruv on:
- The exact return format of `db2_search_tool._run()` (agree on this early)
- The `.env` variable names so both sides use the same keys
- Whether to use `ibm-db` directly or an ORM for Db2 access

---

*Full project context:* `plan/context.md`
*Architecture:* `plan/architecture.md`
*All tasks:* `plan/tasks.md`
*Agent specs:* `plan/agents.md`
*API research:* `plan/api_research.md`
*Dataset spec:* `plan/knowledge_dataset.md`
