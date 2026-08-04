# System Architecture

## Project Name
Airline Delay Management Assistant — Multi-Agent Orchestration

---

## Technology Stack

| Layer           | Technology                          |
|-----------------|--------------------------------------|
| Orchestration   | CrewAI                               |
| Knowledge Store | Haystack + IBM Db2 Vector Store      |
| Document Store  | IBM Db2 Document Store               |
| LLM             | Ollama (local) — `granite3.3` model  |
| API Backend     | FastAPI                              |
| Language        | Python 3.11+                         |
| Config          | python-dotenv + pydantic-settings    |
| Logging         | Python logging + structlog           |
| Testing         | pytest + pytest-asyncio              |

---

## Folder Structure

```
CrewAI_IBM_Db2_Agents/
│
├── plan/                          # Planning docs (not shipped to production)
│   ├── context.md
│   ├── architecture.md
│   ├── tasks.md
│   ├── agents.md
│   ├── api_research.md
│   ├── knowledge_dataset.md
│   └── pawan_context.md
│
├── src/
│   ├── agents/                    # All CrewAI agent definitions
│   │   ├── __init__.py
│   │   ├── operations_manager.py
│   │   ├── weather_agent.py
│   │   ├── flight_agent.py
│   │   ├── passenger_agent.py
│   │   ├── runway_agent.py
│   │   ├── aircraft_agent.py
│   │   ├── rebooking_agent.py
│   │   ├── compensation_agent.py
│   │   ├── decision_agent.py
│   │   └── review_agent.py
│   │
│   ├── tasks/                     # All CrewAI task definitions
│   │   ├── __init__.py
│   │   ├── weather_task.py
│   │   ├── flight_task.py
│   │   ├── passenger_task.py
│   │   ├── runway_task.py
│   │   ├── aircraft_task.py
│   │   ├── rebooking_task.py
│   │   ├── compensation_task.py
│   │   ├── decision_task.py
│   │   └── review_task.py
│   │
│   ├── tools/                     # Shared CrewAI tools
│   │   ├── __init__.py
│   │   ├── db2_search_tool.py     # IBM Db2 Search Tool (Haystack backed)
│   │   ├── weather_tool.py        # External weather API wrapper
│   │   ├── flight_tool.py         # External flight status API wrapper
│   │   └── notification_tool.py   # Notification API wrapper
│   │
│   ├── knowledge/                 # Haystack knowledge pipeline
│   │   ├── __init__.py
│   │   ├── ingestion_pipeline.py  # Document ingestion into Db2
│   │   ├── retrieval_pipeline.py  # Semantic retrieval from Db2
│   │   ├── db2_document_store.py  # IBM Db2 Document Store integration
│   │   └── db2_vector_store.py    # IBM Db2 Vector Store integration
│   │
│   ├── crew/                      # CrewAI Crew assembly and orchestration
│   │   ├── __init__.py
│   │   └── airline_crew.py        # Main Crew definition and kickoff
│   │
│   ├── mock_services/             # Realistic mock enterprise APIs
│   │   ├── __init__.py
│   │   ├── passenger_service.py   # Mock passenger management
│   │   └── fleet_service.py       # Mock fleet/aircraft management
│   │
│   ├── api/                       # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── routes.py              # API routes
│   │   └── schemas.py             # Pydantic request/response models
│   │
│   ├── config/                    # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py            # pydantic-settings config class
│   │
│   ├── data/                      # Enterprise knowledge documents
│   │   ├── sops/
│   │   ├── policies/
│   │   ├── manuals/
│   │   └── faqs/
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py              # Structured logging setup
│
├── tests/
│   ├── test_agents/
│   ├── test_tools/
│   ├── test_knowledge/
│   └── test_api/
│
├── scripts/
│   └── ingest_knowledge.py        # One-time ingestion script
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## System Flow

```
User Request (FastAPI)
        │
        ▼
Operations Manager Agent
  - Plans tasks
  - Creates execution plan
        │
        ▼
 ┌──────────────────────────┐   PARALLEL
 │  Weather Agent           │──────────────────┐
 │  Flight Agent            │                  │
 │  Passenger Agent         │                  │
 └──────────────────────────┘                  │
        │ context passed downstream             │
        ▼                                       │
 ┌──────────────────────────┐   SEQUENTIAL      │
 │  Runway Agent            │◄──────────────────┘
 │  Aircraft Agent          │   (uses weather + flight outputs)
 │  Rebooking Agent         │   (uses passenger + flight outputs)
 └──────────────────────────┘
        │
        ▼
 Decision Agent
   (aggregates all outputs → best course of action)
        │
        ▼
 Compensation Agent
   (uses Decision Agent output + passenger data)
        │
        ▼
 Review Agent
   (validates decision + compensation output)
        │
        ▼
 Final Structured Response → User
```

---

## IBM Db2 Search Tool Flow

```
CrewAI Agent
    │  calls
    ▼
db2_search_tool.run(query="passenger compensation policy")
    │
    ▼
Haystack Retrieval Pipeline
    │
    ├─► Query Embedder  (sentence-transformers/all-MiniLM-L6-v2)
    │
    ├─► Retriever       (IBM Db2 Vector Store — cosine similarity, top-10)
    │
    ├─► Reranker        (cross-encoder/ms-marco-MiniLM-L-6-v2, top-5)
    │
    └─► Answer Builder  (formats top-k document chunks as string)
    │
    ▼
Formatted string returned to agent
```

---

## Context Sharing Strategy

CrewAI tasks are chained via `context=[previous_task]`.

Each task explicitly declares which upstream tasks it depends on.

This ensures:
- No redundant LLM calls
- Every downstream agent builds on prior outputs
- Structured context flows through the pipeline

---

## Work Division

| Area                            | Owner |
|---------------------------------|-------|
| Haystack + IBM Db2 pipeline     | Pawan |
| Enterprise knowledge dataset    | Pawan |
| IBM Db2 Search Tool             | Pawan |
| DB2 Document + Vector Store     | Pawan |
| Ingestion script                | Pawan |
| CrewAI agents (all 10)          | Dhruv |
| CrewAI tasks (all)              | Dhruv |
| CrewAI Crew orchestration       | Dhruv |
| External API tools              | Dhruv |
| Mock enterprise services        | Dhruv |
| FastAPI backend                 | Dhruv |
| Configuration & logging         | Dhruv |
| Testing                         | Both  |
| Documentation / README          | Both  |
