# Task Breakdown

## Work Division Summary

| Owner | Focus Area                                           |
|-------|------------------------------------------------------|
| Dhruv | CrewAI agents, tasks, crew, tools, API, FastAPI      |
| Pawan | Haystack pipeline, IBM Db2 integration, knowledge DB |

---

## DHRUV — Tasks

### D1 · Project Scaffold
- Create folder structure as defined in architecture.md
- Set up `requirements.txt`
- Set up `.env.example`
- Set up `src/config/settings.py` with `pydantic-settings`
- Set up `src/utils/logger.py` with structlog

**Deliverable:** Runnable empty project skeleton

---

### D2 · External API Research & Tools
- Research and compare Weather APIs (OpenWeatherMap, Tomorrow.io, etc.)
- Research and compare Flight Status APIs (AviationStack, FlightAware, etc.)
- Research Airport / Aviation APIs
- Research Notification APIs
- Document findings in `plan/api_research.md`
- Implement `src/tools/weather_tool.py`
- Implement `src/tools/flight_tool.py`
- Implement `src/tools/notification_tool.py`

**Deliverable:** Three working CrewAI-compatible tool wrappers

---

### D3 · Mock Enterprise Services
- Implement `src/mock_services/passenger_service.py`
  - Returns realistic passenger list for a given flight
  - Includes tier, seat, contact, special needs
- Implement `src/mock_services/fleet_service.py`
  - Returns aircraft info (model, capacity, maintenance status)
  - Returns runway availability

**Deliverable:** Two realistic mock services with typed responses

---

### D4 · CrewAI Agents
Implement all 10 agents in `src/agents/`:

| File                    | Agent               | Primary Tools                         |
|-------------------------|---------------------|----------------------------------------|
| operations_manager.py   | Operations Manager  | None (orchestrator only)               |
| weather_agent.py        | Weather Agent       | weather_tool, db2_search_tool          |
| flight_agent.py         | Flight Agent        | flight_tool, db2_search_tool           |
| passenger_agent.py      | Passenger Agent     | passenger_service, db2_search_tool     |
| runway_agent.py         | Runway Agent        | fleet_service, db2_search_tool         |
| aircraft_agent.py       | Aircraft Agent      | fleet_service, db2_search_tool         |
| rebooking_agent.py      | Rebooking Agent     | flight_tool, db2_search_tool           |
| compensation_agent.py   | Compensation Agent  | db2_search_tool                        |
| decision_agent.py       | Decision Agent      | db2_search_tool                        |
| review_agent.py         | Review Agent        | db2_search_tool                        |

Each agent must have:
- `role`
- `goal`
- `backstory`
- `tools` list
- `verbose=True`
- `allow_delegation=False` (except Operations Manager)

**Deliverable:** 10 fully defined CrewAI agents

---

### D5 · CrewAI Tasks
Implement all tasks in `src/tasks/`:

| File                  | Task               | Context (inputs from)               |
|-----------------------|--------------------|--------------------------------------|
| weather_task.py       | WeatherTask        | user_request                         |
| flight_task.py        | FlightTask         | user_request                         |
| passenger_task.py     | PassengerTask      | user_request                         |
| runway_task.py        | RunwayTask         | weather_task, flight_task            |
| aircraft_task.py      | AircraftTask       | weather_task, flight_task            |
| rebooking_task.py     | RebookingTask      | passenger_task, flight_task          |
| compensation_task.py  | CompensationTask   | passenger_task, rebooking_task       |
| decision_task.py      | DecisionTask       | all above tasks                      |
| review_task.py        | ReviewTask         | decision_task                        |

Each task must have:
- `description` (detailed)
- `expected_output` (structured format)
- `agent` assignment
- `context` list (upstream task dependencies)

**Deliverable:** 9 fully defined CrewAI tasks with correct dependency chain

---

### D6 · CrewAI Crew
Implement `src/crew/airline_crew.py`:
- Import all agents and tasks
- Instantiate `Crew` with:
  - `agents` list
  - `tasks` list (in execution order)
  - `process=Process.sequential` or `Process.hierarchical`
  - `verbose=True`
- Expose a `run(flight_query: str) -> str` function
- Log all execution steps

**Deliverable:** Working crew that can be kicked off with a single call

---

### D7 · FastAPI Backend
Implement `src/api/`:
- `schemas.py` — `DelayRequest` and `DelayResponse` Pydantic models
- `routes.py` — `POST /analyze` endpoint
- `main.py` — FastAPI app with startup/shutdown events

The `/analyze` endpoint should:
1. Accept flight delay query
2. Trigger `airline_crew.run()`
3. Return structured agent response

**Deliverable:** Working FastAPI server with one endpoint

---

### D8 · Testing (Dhruv's part)
- Unit tests for each tool
- Integration test for the full crew run (mocked Db2)
- API endpoint tests

---

## PAWAN — Tasks

### P1 · IBM Db2 Setup
- Configure IBM Db2 connection (credentials via `.env`)
- Verify Db2 is accessible
- Create necessary tables/schemas for document store and vector store
- Document setup steps

**Deliverable:** Working Db2 connection and schema

---

### P2 · Enterprise Knowledge Dataset
- Create realistic airline enterprise documents under `src/data/`
- Categories to cover:
  - `sops/` — Standard operating procedures for delays, diversions, cancellations
  - `policies/` — Compensation policy, passenger rights, rebooking rules
  - `manuals/` — Pilot ops manual, crew manual, ground ops manual
  - `faqs/` — Passenger FAQs, crew FAQs, ops FAQs
- Minimum 15–20 documents
- Each document should be plain text or markdown
- Content should be realistic (based on publicly available airline documentation)

**Deliverable:** A rich enterprise knowledge base ready for ingestion

---

### P3 · Haystack Ingestion Pipeline
Implement `src/knowledge/ingestion_pipeline.py`:
- Load documents from `src/data/`
- Clean and normalize text
- Split into chunks (e.g. 512 tokens with 50 token overlap)
- Generate embeddings using HuggingFace or watsonx embeddings
- Store document chunks in IBM Db2 Document Store
- Store embeddings in IBM Db2 Vector Store

Also implement `scripts/ingest_knowledge.py`:
- CLI script to run ingestion end to end
- Logs progress and document counts

**Deliverable:** Ingestion pipeline that populates Db2 with enterprise knowledge

---

### P4 · IBM Db2 Document Store + Vector Store
Implement:
- `src/knowledge/db2_document_store.py` — Haystack-compatible Document Store backed by IBM Db2
- `src/knowledge/db2_vector_store.py` — Vector similarity search in IBM Db2

These should follow Haystack's `DocumentStore` interface.

**Deliverable:** Haystack-compatible Db2 stores

---

### P5 · Haystack Retrieval Pipeline
Implement `src/knowledge/retrieval_pipeline.py`:
- Accept a query string
- Embed the query
- Perform semantic similarity search against IBM Db2 Vector Store
- Retrieve corresponding documents from Document Store
- Return top-k documents

**Deliverable:** Working retrieval pipeline returning relevant docs for any query

---

### P6 · IBM Db2 Search Tool (CrewAI Tool)
Implement `src/tools/db2_search_tool.py`:
- Must subclass `crewai.tools.BaseTool`
- `name`: `"IBM Db2 Enterprise Knowledge Search"`
- `description`: clear description agents use to decide when to call it
- `_run(query: str) -> str`: calls the Haystack retrieval pipeline and formats results
- Returns top 3–5 results as formatted text

**Deliverable:** A plug-and-play CrewAI tool that wraps Haystack retrieval

---

### P7 · Testing (Pawan's part)
- Unit tests for ingestion pipeline
- Unit tests for retrieval pipeline
- Unit test for IBM Db2 Search Tool (mocked Db2)

---

## Integration Milestone (Both)

Once D4–D6 and P3–P6 are done:

1. Run ingestion script to populate Db2
2. Run `airline_crew.run("Flight AI302 from Delhi to London is delayed because of heavy rain. What should we do?")`
3. Verify agents query IBM Db2 Search Tool correctly
4. Verify context flows through agent chain
5. Verify final output is well-structured

---

## Definition of Done

- [ ] All 10 agents defined
- [ ] All 9 tasks defined with correct context chains
- [ ] Crew runs end to end
- [ ] Enterprise knowledge ingested into Db2
- [ ] IBM Db2 Search Tool returns relevant docs
- [ ] FastAPI `/analyze` endpoint works
- [ ] All logs visible during execution
- [ ] README documents setup and run instructions
- [ ] Tests pass
