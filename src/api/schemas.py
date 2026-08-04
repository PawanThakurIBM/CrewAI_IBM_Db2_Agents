"""Pydantic schemas for the FastAPI request/response layer."""
from typing import Literal

from pydantic import BaseModel, Field


class DelayRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        description="Natural-language flight delay report.",
        examples=[
            "Flight AI302 from Delhi to London is delayed because of heavy rain. What should we do?"
        ],
    )


class DelayResponse(BaseModel):
    query: str = Field(description="The original user query.")
    response: str = Field(description="The full reviewed operational response from the crew.")
    elapsed_seconds: float = Field(description="Total crew execution time in seconds.")


# ── SSE event models ──────────────────────────────────────────────────────────

class AgentEvent(BaseModel):
    """Emitted when an agent starts or completes its task."""
    event: Literal["agent_start", "agent_done", "final", "error", "ping"]
    step: int = 0               # 1–9
    total: int = 9
    agent: str = ""
    task: str = ""
    description: str = ""
    output: str = ""            # agent's text output (on agent_done / final)
    elapsed_s: float = 0.0
    message: str = ""           # for error / ping
