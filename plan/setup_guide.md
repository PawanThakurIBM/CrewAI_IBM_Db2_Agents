# Setup Guide — Airline Delay Management Assistant

This guide covers everything needed to run the project from scratch.
Follow all steps in order.

---

## Prerequisites

| Requirement      | Version     | Notes                              |
|------------------|-------------|------------------------------------|
| Python           | 3.11+       | Required                           |
| Ollama           | Latest      | Local LLM runtime                  |
| IBM Db2          | 11.5+       | Cloud Pak for Data or local        |
| git              | Any         |                                    |

---

## Step 1 — Clone the Repository

```bash
git clone git@github-ibm:PawanThakurIBM/CrewAI_IBM_Db2_Agents.git
cd CrewAI_IBM_Db2_Agents
```

---

## Step 2 — Create a Python Virtual Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `sentence-transformers` and `torch` are heavy — this will take a few minutes on first install.

---

## Step 4 — Set Up Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# IBM Db2
DB2_HOST=your-db2-host
DB2_PORT=50000
DB2_DATABASE=BLUDB
DB2_USERNAME=your-username
DB2_PASSWORD=your-password

# External APIs
OPENWEATHER_API_KEY=your-openweathermap-key
AVIATIONSTACK_API_KEY=your-aviationstack-key

# Optional
SENDGRID_API_KEY=your-sendgrid-key
```

**API Keys:**
- `OPENWEATHER_API_KEY` — free at [openweathermap.org](https://openweathermap.org/api)
- `AVIATIONSTACK_API_KEY` — free tier at [aviationstack.com](https://aviationstack.com)
- `SENDGRID_API_KEY` — optional, only for email notifications

**No key needed for:** `aviationweather.gov` (US Gov, free, no auth)

---

## Step 5 — Install and Start Ollama

```bash
# Install Ollama (macOS)
brew install ollama

# Pull the Granite model
ollama pull granite3.3:8b

# Start Ollama (runs on port 11434)
ollama serve
```

Verify it's running:
```bash
curl http://localhost:11434/api/tags
```

---

## Step 6 — Set Up IBM Db2 Schema

Connect to your IBM Db2 instance and create the required schema and tables.

```sql
-- Create schema
CREATE SCHEMA AIRLINE_KB;

-- Document store table
CREATE TABLE AIRLINE_KB.DOCUMENTS (
    id          VARCHAR(255) NOT NULL PRIMARY KEY,
    content     CLOB,
    meta        VARCHAR(4096),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector store table
CREATE TABLE AIRLINE_KB.VECTORS (
    id          VARCHAR(255) NOT NULL PRIMARY KEY,
    doc_id      VARCHAR(255),
    embedding   VARCHAR(32000),
    meta        VARCHAR(4096),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Step 7 — Ingest the Knowledge Base

This populates IBM Db2 with the 20 airline enterprise documents (creates ~57 chunks):

```bash
python scripts/ingest_knowledge.py
```

Expected output:
```
[INFO] Loading documents from src/data/ ...
[INFO] Loaded 20 documents
[INFO] Splitting into chunks (512 tokens / 50 overlap) ...
[INFO] Generated 57 chunks
[INFO] Generating embeddings (all-MiniLM-L6-v2) ...
[INFO] Storing 57 documents in IBM Db2 Document Store ...
[INFO] Storing 57 embeddings in IBM Db2 Vector Store ...
[INFO] Ingestion complete. 57 chunks stored.
```

> Only run this once. Re-running will duplicate chunks unless you clear the tables first.

To reset and re-ingest:
```sql
DELETE FROM AIRLINE_KB.VECTORS;
DELETE FROM AIRLINE_KB.DOCUMENTS;
```

---

## Step 8 — Start the FastAPI Server

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The server starts at `http://127.0.0.1:8000`.

---

## Step 9 — Open the Web UI

Navigate to:
```
http://127.0.0.1:8000/
```

You'll see the Airline Delay Management Assistant UI. Type a delay query and hit **Analyze**.

Example query:
```
Flight AI302 from Delhi to London is delayed because of heavy rain. What should we do?
```

---

## Running Without the Web UI (CLI)

To run the crew directly from the terminal:

```bash
python run_crew.py
```

Or with a custom query:
```python
from src.crew.airline_crew import AirlineCrew

crew = AirlineCrew()
result = crew.run("Flight AI302 from Delhi to London is delayed because of heavy rain.")
print(result)
```

---

## Running Tests

```bash
# All tests
pytest

# Specific test groups
pytest tests/test_knowledge/
pytest tests/test_tools/
pytest tests/test_agents/
pytest tests/test_api/
```

---

## API Endpoints

| Method | Endpoint                   | Description                         |
|--------|----------------------------|-------------------------------------|
| GET    | `/`                        | Serves the web UI                   |
| POST   | `/api/v1/analyze`          | Blocking — returns when crew is done |
| GET    | `/api/v1/analyze/stream`   | SSE stream — streams agent events   |

### Example request:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"flight_query": "Flight AI302 from Delhi to London is delayed due to heavy rain."}'
```

### SSE stream:
```bash
curl -N "http://127.0.0.1:8000/api/v1/analyze/stream?flight_query=Flight+AI302+delayed"
```

---

## Troubleshooting

| Problem                         | Fix                                                                  |
|---------------------------------|----------------------------------------------------------------------|
| `ollama: command not found`     | Install Ollama and ensure `ollama serve` is running                 |
| `granite3.3:8b` model missing   | Run `ollama pull granite3.3:8b`                                     |
| IBM Db2 connection error        | Check `.env` credentials and DB2 host reachability                  |
| `ibm_db` import error           | Run `pip install ibm-db ibm-db-sa`                                  |
| Empty search results            | Re-run `python scripts/ingest_knowledge.py`                         |
| Port 8000 in use                | Run `uvicorn ... --port 8001` and update UI base URL                |
| Slow first startup              | First run downloads embedding model (~90MB) — normal               |

---

## Project Structure Quick Reference

```
src/
├── agents/       ← 10 CrewAI agents
├── tasks/        ← 9 CrewAI tasks
├── tools/        ← IBM Db2 Search Tool + external API tools
├── knowledge/    ← Haystack ingestion + retrieval pipelines
├── mock_services/← Mock PSS, fleet, booking services
├── crew/         ← Crew assembly and kickoff
├── api/          ← FastAPI app, routes, schemas
├── config/       ← Settings (pydantic-settings)
├── data/         ← 20 airline knowledge documents
└── utils/        ← Logging

scripts/
└── ingest_knowledge.py   ← One-time DB population

static/
└── index.html            ← Web UI (Carbon Design System)
```
