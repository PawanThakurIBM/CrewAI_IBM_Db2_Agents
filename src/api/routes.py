"""API routes for the Airline Delay Management Assistant."""
import time

from fastapi import APIRouter, HTTPException

from src.api.schemas import DelayRequest, DelayResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/analyze",
    response_model=DelayResponse,
    summary="Analyze a flight delay situation",
    description=(
        "Submit a flight delay report in natural language. "
        "The multi-agent crew will analyze weather, flight status, passengers, "
        "aircraft, runway, rebooking options, and compensation entitlements, "
        "then return a fully reviewed operational response."
    ),
)
async def analyze_delay(request: DelayRequest) -> DelayResponse:
    logger.info("analyze_endpoint_called", query=request.query)
    start = time.time()
    try:
        # Import here to avoid circular imports at module load time
        from src.crew.airline_crew import run as crew_run
        response = crew_run(request.query)
        elapsed = round(time.time() - start, 2)
        logger.info("analyze_endpoint_success", elapsed_seconds=elapsed)
        return DelayResponse(query=request.query, response=response, elapsed_seconds=elapsed)
    except Exception as exc:
        logger.error("analyze_endpoint_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Crew execution failed: {exc}") from exc


@router.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok", "service": "Airline Delay Management Assistant"}
