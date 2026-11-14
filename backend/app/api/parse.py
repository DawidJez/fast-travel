"""HTTP route for AI trip parsing. HTTP only — all logic lives in app.services.parsing."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app import config
from app.schemas import ParseRequest, ParseResponse
from app.services import parsing

router = APIRouter(prefix="/api", tags=["parse"])


def get_llm_client() -> parsing.LLMClient:
    """Dependency: GeminiClient when an API key is configured, otherwise DemoClient.
    Overridden in tests so they never call the real API."""
    if config.GEMINI_API_KEY is None:
        return parsing.DemoClient()
    return parsing.GeminiClient(api_key=config.GEMINI_API_KEY, model=config.GEMINI_MODEL)


LLMDep = Annotated[parsing.LLMClient, Depends(get_llm_client)]


@router.post("/parse", response_model=ParseResponse)
def parse_trip(data: ParseRequest, llm: LLMDep):
    """Free text -> fields to prefill the trip form. Writes nothing to the database."""
    result = parsing.parse_trip_text(data.text, llm)
    return ParseResponse(**result.trip.model_dump(), source=result.source)
