"""Pydantic schemas for the FastAPI request/response layer."""
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
