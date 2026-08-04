"""
FastAPI application entry point.

Run with:
    uvicorn src.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: D401
    logger.info("app_started", version="1.0.0")
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="Airline Delay Management Assistant",
    description=(
        "Multi-agent AI system built with CrewAI + Haystack + IBM Db2. "
        "Orchestrates 10 specialized agents to produce a comprehensive operational "
        "response to any airline flight delay scenario."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
