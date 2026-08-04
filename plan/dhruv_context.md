# Dhruv's Context — Airline Delay Management Assistant

This is your owner's reference document. Keep it up to date as the project evolves.

---

## What We're Building

A **production-grade multi-agent AI system** called the **Airline Delay Management Assistant**.

10 specialized CrewAI agents collaborate to handle airline flight delays. When a user reports a delayed flight, agents work in parallel and sequentially — each solving one piece of the problem — and produce a consolidated operational response streamed back in real time via SSE.

**Example query:**
```
Flight AI302 from Delhi to London is delayed because of heavy rain. What should we do?
```

---

## Current State — What's Built

The project is **fully implemented and running end-to-end.**

### ✅ Your completed work:
- All 10 CrewAI agents (`src/agents/`)
- All 9 CrewAI tasks with correct context chains (`src/tasks/`)
- Crew orchestration with per-task callbacks (`src/crew/airline_crew.py`)
- External API tools: weather, flight, airport (`src/tools/`)
- Mock enterprise services: passenger, fleet, booking (`src/mock_services/`)
- FastAPI backend + SSE streaming (`src/api/`)
- Carbon Design System web UI (`static/index.html`)
- Configuration and noise-suppressed logging (`src/config/`, `src/utils/`)

### ✅ Pawan's completed work (your dependency):
- IBM Db2 schema (AIRLINE_KB.DOCUMENTS + AIRLINE_KB.VECTORS)
- 20 airline enterprise knowledge documents (`src/data/`)
- Haystack ingestion pipeline + CLI script
- IBM Db2 Document Store + Vector Store
- Haystack retrieval pipeline (embed → cosine → rerank)
- IBM Db2 Search Tool (`src/tools/db2_search_tool.py`)
- Tests for knowledge pipeline and search tool

### ⬜ Remaining work (yours):
- `tests/test_agents/` — unit tests for agents
- `tests/test_api/` — endpoint tests for FastAPI
- Optional: `notification_tool.py` (SendGrid email alerts, not on critical path)

---

## Technology Stack

| Component       | Technology                                  |
|-----------------|---------------------------------------------|
| Orchestration   | CrewAI                                      |
| LLM             | `ollama/granite3.3:8b` (plain string, NOT LangChain) |
| Knowledge Store | Haystack + IBM Db2                          |
| API Backend     | FastAPI                                     |
| Language        | Python 3.11+                                |
| Embeddings      | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| Reranker        | `cross-encoder/ms-marco-MiniLM-L-6-v2`     |
| Web UI          | Carbon Design System (static/index.html)    |

---

## Architecture Overview

```
User Request (http://127.0.0.1:8000/)
         │
         ▼
POST /api/v1/analyze/stream  ─── FastAPI SSE
         │
         ▼
AirlineCrew.run(flight_query)
         │
         ▼
Operations Manager (orchestrator, allow_delegation=True)
         │
    ┌────┴────┐
    ▼         ▼
Weather     Flight     Passenger     ← parallel (step 1)
Agent       Agent      Agent
    │         │            │
    └────┬────┘     ┌──────┘
         ▼           ▼
    Runway      Aircraft      Rebooking  ← sequential (step 2)
    Agent        Agent         Agent
         │
         ▼
    Decision Agent  ──►  Compensation Agent  ← sequential (step 3)
         │
         ▼
    Review Agent  ──►  Final Response        ← sequential (step 4)

  ─────────────────────────────────────────
  ALL AGENTS  ──►  db2_search_tool  (Pawan)
  ─────────────────────────────────────────
```

---

## Your Files — What You Own

```
src/
├── agents/
│   ├── _llm.py                     ← llm = "ollama/granite3.3:8b"
│   ├── operations_manager.py
│   ├── weather_agent.py
│   ├── flight_agent.py
│   ├── passenger_agent.py
│   ├── runway_agent.py
│   ├── aircraft_agent.py
│   ├── rebooking_agent.py
│   ├── compensation_agent.py
│   ├── decision_agent.py
│   └── review_agent.py
│
├── tasks/
│   ├── weather_task.py
│   ├── flight_task.py
│   ├── passenger_task.py
│   ├── runway_task.py             ← context=[weather_task, flight_task]
│   ├── aircraft_task.py           ← context=[weather_task, flight_task]
│   ├── rebooking_task.py          ← context=[passenger_task, flight_task]
│   ├── compensation_task.py       ← context=[passenger_task, rebooking_task]
│   ├── decision_task.py           ← context=[ALL above]
│   └── review_task.py             ← context=[decision_task]
│
├── tools/
│   ├── weather_tool.py            ← OpenWeatherMap + aviationweather.gov
│   ├── flight_tool.py             ← AviationStack + OpenSky
│   └── airport_tool.py            ← aviationweather.gov NOTAMs
│
├── mock_services/
│   ├── passenger_service.py       ← mock PSS (manifest, VIP, UM, WCHR)
│   ├── fleet_service.py           ← mock fleet (aircraft, MEL, rotation)
│   └── booking_service.py         ← mock booking (seat inventory, rebooking)
│
├── crew/
│   └── airline_crew.py            ← Crew assembly, callbacks, run()
│
├── api/
│   ├── main.py                    ← FastAPI app, serves static/
│   ├── routes.py                  ← POST /api/v1/analyze + SSE stream
│   └── schemas.py                 ← DelayRequest, DelayResponse, AgentEvent
│
├── config/
│   └── settings.py                ← pydantic-settings
│
└── utils/
    └── logger.py                  ← structured logging, noise suppression

static/
└── index.html                     ← Carbon Design System UI (served at /)
```

---

## Key Technical Decisions (Already Locked)

### LLM
```python
# src/agents/_llm.py
llm = "ollama/granite3.3:8b"   # plain string — CrewAI v1.x format, no LangChain
```
Do NOT use `langchain_community.llms.Ollama`. CrewAI v1.x takes the plain string.

### Tool Contract with Pawan
`db2_search_tool._run()` always returns a **plain string**.

Format:
```
[Document 1 — filename.md]
<content>

[Document 2 — filename.md]
<content>
```

### Context Chaining
Tasks are chained via `context=[task_a, task_b]`. The downstream agent's LLM automatically receives the upstream outputs as context — no manual wiring needed.

### SSE Events
Each task callback fires `AgentEvent` objects that are pushed to the SSE stream. Event types: `agent_start`, `agent_done`, `final`, `error`.

### Arrow Lighting in UI
The UI has 5 animated pipeline arrows. Steps 1–3 light arrow-0, steps 4–6 light arrow-1, step 7 lights arrow-2, step 8 lights arrow-3, step 9 lights arrow-4.

### Session Persistence
`localStorage` key: `airline_assistant_session` — saves after every `agent_done` + `final` event. 2-hour expiry. Restored on page load.

---

## API Endpoints

| Method | Endpoint                       | Description                          |
|--------|--------------------------------|--------------------------------------|
| GET    | `/`                            | Serves `static/index.html`           |
| POST   | `/api/v1/analyze`              | Blocking — full crew run             |
| GET    | `/api/v1/analyze/stream`       | SSE — streams `AgentEvent` objects   |

---

## External APIs Used

| Tool             | API                              | Auth              |
|------------------|----------------------------------|-------------------|
| `weather_tool`   | OpenWeatherMap + aviationweather.gov | API key + none |
| `flight_tool`    | AviationStack + OpenSky          | API key + none    |
| `airport_tool`   | aviationweather.gov NOTAMs       | None              |

Keys go in `.env` as `OPENWEATHER_API_KEY` and `AVIATIONSTACK_API_KEY`.

---

## Running the Project

```bash
# Start Ollama (separate terminal)
ollama serve

# Start FastAPI (project root, venv active)
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Open UI
open http://127.0.0.1:8000/

# Or run crew directly
python run_crew.py
```

---

## Agent Execution Order (for reference)

```
Step 0:  Operations Manager  (creates plan)
Step 1:  Weather Agent       (parallel)
Step 2:  Flight Agent        (parallel)
Step 3:  Passenger Agent     (parallel)
Step 4:  Runway Agent        (← weather + flight)
Step 5:  Aircraft Agent      (← weather + flight)
Step 6:  Rebooking Agent     (← passenger + flight)
Step 7:  Decision Agent      (← all above)
Step 8:  Compensation Agent  (← decision + passenger)
Step 9:  Review Agent        (← decision)
```

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
| `pawan_context.md`     | Pawan's onboarding doc (what to send him)                 |
