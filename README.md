# Airline Delay Management Assistant

**Multi-Agent Orchestration with CrewAI + Haystack + IBM Db2**

A production-grade demonstration of enterprise multi-agent AI orchestration.
When a flight delay is reported, 10 specialized AI agents collaborate — analyzing weather,
flight status, passengers, aircraft, runways, rebooking, and compensation — and produce
a single reviewed operational response.

---

## Architecture

```
User Request (FastAPI)
        │
        ▼
Operations Manager Agent
        │
   ┌────┼────┐
   ▼    ▼    ▼
Weather Flight Passenger   ← parallel
   │    │    │
   ▼    ▼    ▼
Runway Aircraft Rebooking  ← sequential (use upstream context)
        │
        ▼
   Decision Agent           ← synthesises everything
        │
        ▼
  Compensation Agent        ← uses Decision + Passenger outputs
        │
        ▼
    Review Agent            ← final QA → approved response
```

**Knowledge Layer (Pawan):** All agents query IBM Db2 via the `IBM Db2 Search Tool`,
which uses a Haystack retrieval pipeline (embedder → retriever → reranker).

---

## Technology Stack

| Component     | Technology                            |
|---------------|---------------------------------------|
| Orchestration | CrewAI                                |
| LLM           | Ollama `granite3.3` (local)           |
| Knowledge     | Haystack 2.x + IBM Db2                |
| Embeddings    | `sentence-transformers/all-MiniLM-L6-v2` |
| Reranker      | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| API Backend   | FastAPI                               |
| Language      | Python 3.11+                          |

---

## Project Structure

```
src/
├── agents/          ← 10 CrewAI agents
├── tasks/           ← 9 CrewAI tasks with context chains
├── tools/           ← weather_tool, flight_tool, airport_tool, db2_search_tool
├── crew/            ← airline_crew.py (main orchestrator)
├── mock_services/   ← passenger, fleet, booking mock services
├── knowledge/       ← Haystack pipelines + IBM Db2 stores (Pawan)
├── api/             ← FastAPI app
├── config/          ← pydantic-settings
├── data/            ← enterprise knowledge documents (Pawan)
└── utils/           ← structlog logging
```

---

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running locally
- Granite model pulled: `ollama pull granite3.3`
- IBM Db2 instance (for knowledge retrieval — Pawan's setup)
- API keys for OpenWeatherMap and AviationStack (free tier)

---

## Setup

```bash
# 1. Clone the repository
git clone git@github-ibm:PawanThakurIBM/CrewAI_IBM_Db2_Agents.git
cd CrewAI_IBM_Db2_Agents

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your API keys and Db2 credentials

# 5. Verify Ollama is running with Granite
ollama list   # should show granite3.3
```

---

## Running the API Server

```bash
uvicorn src.api.main:app --reload --port 8000
```

Then open: http://localhost:8000/docs

---

## Making a Request

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Flight AI302 from Delhi to London is delayed because of heavy rain. What should we do?"
  }'
```

---

## Knowledge Ingestion (Pawan's step)

Once Pawan has created the knowledge documents and set up IBM Db2:

```bash
python scripts/ingest_knowledge.py
```

This loads all documents from `src/data/`, generates embeddings, and stores them in IBM Db2.

---

## Environment Variables

| Variable                | Description                          | Required |
|-------------------------|--------------------------------------|----------|
| `OLLAMA_BASE_URL`        | Ollama server URL                    | Yes      |
| `OLLAMA_MODEL`           | Model name (e.g. `granite3.3`)       | Yes      |
| `OPENWEATHER_API_KEY`    | OpenWeatherMap API key               | Yes      |
| `AVIATIONSTACK_API_KEY`  | AviationStack API key                | Yes      |
| `DB2_HOST`               | IBM Db2 host                         | Yes (knowledge retrieval) |
| `DB2_PORT`               | IBM Db2 port (default 50000)         | Yes      |
| `DB2_DATABASE`           | Database name                        | Yes      |
| `DB2_USERNAME`           | Db2 username                         | Yes      |
| `DB2_PASSWORD`           | Db2 password                         | Yes      |
| `SENDGRID_API_KEY`       | SendGrid key (optional notifications)| No       |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Work Division

| Area                         | Owner |
|------------------------------|-------|
| CrewAI agents, tasks, crew   | Dhruv |
| External API tools           | Dhruv |
| Mock enterprise services     | Dhruv |
| FastAPI backend              | Dhruv |
| Haystack ingestion pipeline  | Pawan |
| IBM Db2 document + vector store | Pawan |
| Haystack retrieval pipeline  | Pawan |
| IBM Db2 Search Tool          | Pawan |
| Enterprise knowledge dataset | Pawan |
| Testing                      | Both  |

---

## Integration Point

Dhruv's agents call `src/tools/db2_search_tool.py`.
Pawan implements the full retrieval in `src/knowledge/retrieval_pipeline.py`
and plugs it into `db2_search_tool._run()`.

Once Pawan's pipeline is ready, replace the stub `_run()` body with:
```python
from src.knowledge.retrieval_pipeline import retrieve
return retrieve(query)
```
