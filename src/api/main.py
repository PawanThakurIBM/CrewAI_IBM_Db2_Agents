"""
FastAPI application entry point.

Run with:
    uvicorn src.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: D401
    logger.info("app_started", version="1.0.0", ui=str(_STATIC_DIR))
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

# Serve the frontend UI
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_ui():
        return FileResponse(str(_STATIC_DIR / "index.html"))
