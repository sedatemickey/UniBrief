"""Unit tests for the real OpenAI SDK adapter without spending tokens."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

from app.ai import OpenAICompatibleProvider, ProviderError
from app.core.config import Settings


class FakeCompletions:
    """Test transport surface matching AsyncOpenAI Chat Completions."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome

    async def create(self, **_kwargs: Any) -> Any:
        """Return or raise one SDK-shaped outcome."""

        if isinstance(self.outcome, Exception):
            raise self.outcome
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.outcome))]
        )


class FakeClient:
    """Minimal async SDK client used only at the transport boundary."""

    def __init__(self, outcome: Any) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(outcome))
        self.closed = False

    async def close(self) -> None:
        """Record provider cleanup."""

        self.closed = True


def _provider(
    monkeypatch: pytest.MonkeyPatch, outcome: Any
) -> tuple[OpenAICompatibleProvider, FakeClient]:
    settings = Settings(ai_api_key="secret-test-key", ai_default_model="model-a")
    provider = OpenAICompatibleProvider(settings)
    client = FakeClient(outcome)
    monkeypatch.setattr(provider, "_client", lambda: client)
    return provider, client


def _analyze(provider: OpenAICompatibleProvider) -> Any:
    return asyncio.run(
        provider.analyze(
            model="model-a",
            messages=[{"role": "user", "content": "test"}],
        )
    )


def test_provider_parses_strict_json_and_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, client = _provider(monkeypatch, '{"useful":false,"items":[]}')
    result = _analyze(provider)
    assert result.value.useful is False
    assert result.raw_response_text == '{"useful":false,"items":[]}'
    assert client.closed is True


@pytest.mark.parametrize(
    "raw_text",
    [
        "not-json",
        '{"useful":true,"items":[]}',
        '{"useful":false,"items":[],"unexpected":1}',
    ],
)
def test_provider_rejects_invalid_json_or_schema(
    monkeypatch: pytest.MonkeyPatch, raw_text: str
) -> None:
    provider, _client = _provider(monkeypatch, raw_text)
    with pytest.raises(ProviderError) as captured:
        _analyze(provider)
    assert captured.value.code == "INVALID_AI_OUTPUT"
    assert captured.value.http_status == 502


def _status_error(error_type: type[Exception], status: int, message: str) -> Exception:
    request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx.Response(status, request=request, json={"error": {"message": message}})
    return error_type(message, response=response, body={"error": {"message": message}})  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("exception", "code", "status"),
    [
        (_status_error(AuthenticationError, 401, "bad key"), "AUTH_ERROR", 502),
        (_status_error(NotFoundError, 404, "model not found"), "MODEL_NOT_FOUND", 502),
        (_status_error(RateLimitError, 429, "rate"), "RATE_LIMITED", 429),
        (
            APITimeoutError(
                httpx.Request("POST", "https://provider.example/v1/chat/completions")
            ),
            "TIMEOUT",
            504,
        ),
        (
            APIConnectionError(
                request=httpx.Request(
                    "POST", "https://provider.example/v1/chat/completions"
                )
            ),
            "NETWORK_ERROR",
            502,
        ),
    ],
)
def test_provider_maps_sdk_errors(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    code: str,
    status: int,
) -> None:
    provider, _client = _provider(monkeypatch, exception)
    with pytest.raises(ProviderError) as captured:
        _analyze(provider)
    assert captured.value.code == code
    assert captured.value.http_status == status
    assert "secret-test-key" not in captured.value.message

