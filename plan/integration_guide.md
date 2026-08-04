# Integration Guide — Dhruv ↔ Pawan

This document describes the exact contracts between the two work streams so integration is smooth and unambiguous.

---

## The Single Integration Point

There is one file that connects both sides:

```
src/tools/db2_search_tool.py
```

**Dhruv uses it** — every agent imports `db2_search_tool` and passes it in the `tools` list.
**Pawan builds it** — it wraps the Haystack retrieval pipeline backed by IBM Db2.

If this file works correctly, both sides work correctly.

---

## Contract: `db2_search_tool._run()`

### Signature
```python
def _run(self, query: str) -> str:
```

### Input
A plain English query string. The agent decides what to ask.

Examples:
```
"passenger compensation policy for 3-hour delay"
"de-icing procedures and holdover times"
"EU261 cash compensation amounts"
"crew FDP limits during extended delay"
```

### Output
A **plain string** (not a list, not a dict, not JSON). CrewAI tools must always return strings.

Format:
```
[Document 1 — compensation_policy.md]
For delays exceeding 3 hours on EU routes, passengers are entitled to cash compensation...

[Document 2 — eu261_2004_regulation.md]
Article 7 specifies compensation of €250 for flights under 1500km, €400 for flights...

[Document 3 — passenger_rights_policy.md]
Airlines must provide meals and refreshments after a delay of 2 hours or more...
```

### Rules
1. Always returns a string — never raises an exception to the caller
2. If nothing is found, returns a descriptive fallback string: `"No relevant documents found for: {query}"`
3. Returns 3–5 documents maximum
4. Each document block starts with `[Document N — filename.md]`
5. Source filename is the actual `.md` file basename from `src/data/`

---

## Contract: IBM Db2 Tables

Both sides depend on these two tables existing in IBM Db2 under the `AIRLINE_KB` schema:

| Table                    | Owner      | Purpose                          |
|--------------------------|------------|----------------------------------|
| `AIRLINE_KB.DOCUMENTS`   | Pawan      | Raw text chunks + metadata       |
| `AIRLINE_KB.VECTORS`     | Pawan      | 384-dim embeddings (all-MiniLM)  |

The schema must be created before ingestion. See `plan/setup_guide.md` Step 6.

---

## Contract: Embedding Model

| Property        | Value                                        |
|-----------------|----------------------------------------------|
| Model           | `sentence-transformers/all-MiniLM-L6-v2`     |
| Dimensions      | 384                                          |
| Used for        | Both ingestion (Pawan) AND query embedding   |
| Source          | HuggingFace (downloaded at first run)        |

**Do not change this model** — changing it invalidates all stored vectors and requires re-ingestion.

---

## Contract: Reranker Model

| Property        | Value                                        |
|-----------------|----------------------------------------------|
| Model           | `cross-encoder/ms-marco-MiniLM-L-6-v2`      |
| Used for        | Reranking top-10 retrieved docs to top-5     |
| Source          | HuggingFace                                  |

---

## Contract: Environment Variables

Both sides read from the same `.env` file. These are the variables that matter for integration:

```env
# IBM Db2 — used by Pawan's knowledge pipeline AND by all agents at runtime
DB2_HOST=
DB2_PORT=
DB2_DATABASE=
DB2_USERNAME=
DB2_PASSWORD=
```

The `settings.py` config class (`src/config/settings.py`) reads these via `pydantic-settings`.

---

## How Dhruv's Agents Use the Tool

Every agent receives `db2_search_tool` in its `tools` list:

```python
from src.tools.db2_search_tool import db2_search_tool

weather_agent = Agent(
    role="Aviation Meteorologist",
    goal="...",
    tools=[weather_tool, db2_search_tool],
    llm=llm,
    verbose=True,
)
```

Agents call the tool by name — the LLM decides when to invoke it based on the tool's `description`.
The tool description guides the agent: *"Use this tool to look up airline policies, SOPs, regulations, or procedures from the IBM Db2 knowledge base."*

---

## How Pawan's Tool Calls Haystack

```
db2_search_tool._run(query)
        │
        ▼
retrieval_pipeline.retrieve(query)
        │
        ├─ embed query with all-MiniLM-L6-v2
        ├─ cosine similarity search → AIRLINE_KB.VECTORS (top-10)
        ├─ rerank with ms-marco-MiniLM-L-6-v2 (top-5)
        └─ fetch text from AIRLINE_KB.DOCUMENTS
        │
        ▼
formatted string → returned to agent
```

---

## Integration Test — Verify It Works

After both ingestion and crew setup are done, run this quick check:

```python
from src.tools.db2_search_tool import db2_search_tool

result = db2_search_tool._run("What compensation is a passenger entitled to after a 3-hour delay?")
print(result)
```

Expected: 3–5 document blocks with relevant content from `compensation_policy.md`, `eu261_2004_regulation.md`, or `passenger_rights_policy.md`.

---

## Full End-to-End Integration Flow

```
1. Pawan runs:   python scripts/ingest_knowledge.py
                 → 20 docs → 57 chunks → stored in AIRLINE_KB

2. Dhruv runs:   uvicorn src.api.main:app --reload
                 → FastAPI starts at :8000

3. User sends:   POST /api/v1/analyze/stream
                 → crew.run() kicks off

4. Agent calls:  db2_search_tool._run("de-icing SOP for heavy rain")
                 → Haystack retrieves → Db2 → returns string

5. Agent uses:   retrieved context in its task output

6. Crew completes → Final response streamed back to UI
```

---

## What to Do If Integration Breaks

| Symptom                          | Likely Cause                         | Fix                               |
|----------------------------------|--------------------------------------|-----------------------------------|
| Tool returns empty string        | Db2 tables are empty                 | Re-run `ingest_knowledge.py`      |
| Tool raises `ibm_db` error       | Db2 connection failed                | Check `.env` credentials          |
| Tool returns wrong format        | `_run()` returning list, not string  | Check `db2_search_tool.py`        |
| Agents never call the tool       | Wrong tool description               | Update description in search tool |
| Embeddings mismatch              | Different model used at ingest time  | Re-ingest with correct model      |

---

## Sync Points Between Dhruv and Pawan

These are decisions that must be agreed before independent work starts:

| Decision                              | Agreed Value                              |
|---------------------------------------|-------------------------------------------|
| Tool return type                      | `str` (always)                            |
| Tool output format                    | `[Document N — filename.md]\n<content>`   |
| Embedding model                       | `all-MiniLM-L6-v2` (384-dim)             |
| Reranker model                        | `ms-marco-MiniLM-L-6-v2`                 |
| Db2 schema name                       | `AIRLINE_KB`                              |
| Document table                        | `AIRLINE_KB.DOCUMENTS`                    |
| Vector table                          | `AIRLINE_KB.VECTORS`                      |
| Top-k retrieval                       | 10 from vector store, 5 after rerank      |
| Chunk size                            | 512 tokens / 50 overlap                   |

All these are already implemented and locked. Do not change them without coordinating with both sides.
