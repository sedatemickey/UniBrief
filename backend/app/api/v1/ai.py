"""Authenticated OpenAI-compatible configuration and connectivity routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import current_user, user_csrf
from app.models import User
from app.schemas.ai import (
    AIConfigResponse,
    AIModelsResponse,
    AITestRequest,
    AITestResponse,
)
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/config", response_model=AIConfigResponse)
def ai_config(_user: Annotated[User, Depends(current_user)]) -> AIConfigResponse:
    """Return safe server AI settings without the API Key."""

    return ai_service.safe_config()


@router.get("/models", response_model=AIModelsResponse)
async def ai_models(_user: Annotated[User, Depends(current_user)]) -> AIModelsResponse:
    """Load model IDs or return the documented manual-input fallback."""

    return await ai_service.models()


@router.post("/test", response_model=AITestResponse)
async def ai_test(
    payload: AITestRequest,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> AITestResponse:
    """Perform one rate-limited, real, potentially billable provider request."""

    return await ai_service.test_connection(user.id, payload.model)
