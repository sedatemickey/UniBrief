"""Safe AI configuration, model listing, and real connection-test operations."""

from __future__ import annotations

import asyncio
import time

from app.ai import OpenAICompatibleProvider, ProviderError
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.ai import (
    AIConfigResponse,
    AIModelsResponse,
    AIModelSummary,
    AITestResponse,
)

_TEST_INTERVAL_SECONDS = 10
_test_lock = asyncio.Lock()
_last_test_by_user: dict[int, float] = {}


def provider() -> OpenAICompatibleProvider:
    """Construct the runtime provider from server-only environment settings."""

    return OpenAICompatibleProvider()


def resolve_model(requested: str | None) -> str:
    """Resolve an explicit model before the server default."""

    model = (requested or "").strip() or get_settings().ai_default_model.strip()
    if not model:
        raise AppError(400, "AI_MODEL_REQUIRED", "请选择模型或配置 AI_DEFAULT_MODEL")
    return model


def safe_config() -> AIConfigResponse:
    """Return non-secret AI configuration for the ordinary user UI."""

    settings = get_settings()
    return AIConfigResponse(
        base_url=settings.ai_base_url,
        default_model=settings.ai_default_model,
        timeout_seconds=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
        has_api_key=bool(settings.ai_api_key.strip()),
    )


async def models() -> AIModelsResponse:
    """List provider models while preserving manual-model fallback."""

    try:
        ids = await provider().list_models()
    except ProviderError as exc:
        if exc.code == "MODEL_LIST_UNSUPPORTED":
            return AIModelsResponse(
                supports_listing=False,
                models=[],
                error_code=exc.code,
                message=exc.message,
            )
        raise _app_error(exc) from exc
    return AIModelsResponse(
        supports_listing=True,
        models=[AIModelSummary(id=item) for item in sorted(set(ids))],
    )


async def test_connection(user_id: int, requested_model: str | None) -> AITestResponse:
    """Rate-limit and perform one real, potentially billable provider request."""

    model = resolve_model(requested_model)
    async with _test_lock:
        now = time.monotonic()
        previous = _last_test_by_user.get(user_id)
        if previous is not None and now - previous < _TEST_INTERVAL_SECONDS:
            raise AppError(
                429,
                "AI_TEST_RATE_LIMITED",
                "连接测试过于频繁，请稍后再试",
                retryable=True,
                details={"retry_after_seconds": _TEST_INTERVAL_SECONDS},
            )
        _last_test_by_user[user_id] = now
    try:
        latency_ms = await provider().test_connection(model)
    except ProviderError as exc:
        raise _app_error(exc) from exc
    return AITestResponse(model=model, latency_ms=latency_ms)


def _app_error(exc: ProviderError) -> AppError:
    return AppError(
        exc.http_status,
        exc.code,
        exc.message,
        retryable=exc.retryable,
    )

