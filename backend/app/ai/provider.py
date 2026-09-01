"""Real OpenAI-compatible provider implemented with the official async SDK."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.schemas.ai import AIMessageOutput

_MAX_RAW_TEXT = 65535


@dataclass(frozen=True)
class ProviderResult[T: BaseModel]:
    """A validated provider result plus auditable non-secret metadata."""

    value: T
    raw_response_text: str
    latency_ms: int


class ProviderError(Exception):
    """Classified provider failure with the fixed public HTTP mapping."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int,
        retryable: bool,
        latency_ms: int | None = None,
        raw_response_text: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        self.latency_ms = latency_ms
        self.raw_response_text = raw_response_text


class OpenAICompatibleProvider:
    """Call Chat Completions and Models using server-only credentials."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> AsyncOpenAI:
        """Create an SDK client without exposing its credential."""

        if not self.settings.ai_api_key.strip():
            raise ProviderError(
                "AUTH_ERROR",
                "服务端尚未配置 AI API Key",
                http_status=502,
                retryable=False,
            )
        return AsyncOpenAI(
            api_key=self.settings.ai_api_key,
            base_url=self.settings.ai_base_url.rstrip("/"),
            timeout=float(self.settings.ai_timeout_seconds),
            max_retries=self.settings.ai_max_retries,
        )

    async def list_models(self) -> list[str]:
        """Return sorted unique model IDs or classify an unsupported endpoint."""

        client = self._client()
        started = time.perf_counter()
        try:
            page = await client.models.list()
            ids = sorted({str(item.id) for item in page.data if getattr(item, "id", None)})
            return ids
        except APIStatusError as exc:
            if exc.status_code in {404, 405, 501}:
                raise ProviderError(
                    "MODEL_LIST_UNSUPPORTED",
                    "当前兼容服务不支持模型列表，请手工输入模型 ID",
                    http_status=200,
                    retryable=False,
                    latency_ms=_elapsed_ms(started),
                ) from exc
            raise self._map_exception(exc, started, context="models") from exc
        except Exception as exc:
            raise self._map_exception(exc, started, context="models") from exc
        finally:
            await client.close()

    async def test_connection(self, model: str) -> int:
        """Issue the documented minimal real request and return latency."""

        client = self._client()
        started = time.perf_counter()
        try:
            await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with OK only."}],
                max_tokens=8,
            )
            return _elapsed_ms(started)
        except Exception as exc:
            raise self._map_exception(exc, started, context="chat") from exc
        finally:
            await client.close()

    async def analyze(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
    ) -> ProviderResult[AIMessageOutput]:
        """Call Chat Completions and strictly validate the returned JSON object."""

        client = self._client()
        started = time.perf_counter()
        raw_text: str | None = None
        try:
            completion = await self._create_completion(client, model, messages, use_json=True)
            raw_text = _completion_text(completion)
            return ProviderResult(
                value=_validate_output(raw_text),
                raw_response_text=raw_text[:_MAX_RAW_TEXT],
                latency_ms=_elapsed_ms(started),
            )
        except BadRequestError as exc:
            if self.settings.ai_json_mode == "auto" and _json_mode_unsupported(exc):
                try:
                    completion = await self._create_completion(
                        client, model, messages, use_json=False
                    )
                    raw_text = _completion_text(completion)
                    return ProviderResult(
                        value=_validate_output(raw_text),
                        raw_response_text=raw_text[:_MAX_RAW_TEXT],
                        latency_ms=_elapsed_ms(started),
                    )
                except (json.JSONDecodeError, ValidationError, ValueError) as parse_exc:
                    raise _invalid_output(parse_exc, started, raw_text) from parse_exc
                except Exception as fallback_exc:
                    raise self._map_exception(
                        fallback_exc, started, context="chat", raw_text=raw_text
                    ) from fallback_exc
            raise self._map_exception(exc, started, context="chat", raw_text=raw_text) from exc
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise _invalid_output(exc, started, raw_text) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise self._map_exception(exc, started, context="chat", raw_text=raw_text) from exc
        finally:
            await client.close()

    async def _create_completion(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict[str, str]],
        *,
        use_json: bool,
    ) -> Any:
        """Perform one compatible Chat Completions request."""

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self.settings.ai_temperature,
        }
        if use_json and self.settings.ai_json_mode != "off":
            kwargs["response_format"] = {"type": "json_object"}
        return await client.chat.completions.create(**kwargs)

    def _map_exception(
        self,
        exc: Exception,
        started: float,
        *,
        context: str,
        raw_text: str | None = None,
    ) -> ProviderError:
        """Map SDK exceptions without ever returning upstream credentials."""

        latency = _elapsed_ms(started)
        message = _sanitize_error(str(exc), self.settings.ai_api_key)
        if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
            return ProviderError(
                "AUTH_ERROR", "AI API Key 无效或无权限", http_status=502, retryable=False,
                latency_ms=latency, raw_response_text=_safe_raw(raw_text)
            )
        if isinstance(exc, RateLimitError):
            return ProviderError(
                "RATE_LIMITED", "AI 服务请求过于频繁", http_status=429, retryable=True,
                latency_ms=latency, raw_response_text=_safe_raw(raw_text)
            )
        if isinstance(exc, APITimeoutError):
            return ProviderError(
                "TIMEOUT", "AI 服务请求超时", http_status=504, retryable=True,
                latency_ms=latency, raw_response_text=_safe_raw(raw_text)
            )
        if isinstance(exc, APIConnectionError):
            return ProviderError(
                "NETWORK_ERROR", "无法连接 AI 服务", http_status=502, retryable=True,
                latency_ms=latency, raw_response_text=_safe_raw(raw_text)
            )
        if context == "chat" and (
            isinstance(exc, NotFoundError) or _looks_like_model_not_found(exc)
        ):
            return ProviderError(
                "MODEL_NOT_FOUND", "所选 AI 模型不存在或不可用", http_status=502,
                retryable=False, latency_ms=latency, raw_response_text=_safe_raw(raw_text)
            )
        if isinstance(exc, APIStatusError):
            return ProviderError(
                "PROVIDER_ERROR",
                message or "AI 服务返回错误",
                http_status=502,
                retryable=exc.status_code >= 500,
                latency_ms=latency,
                raw_response_text=_safe_raw(raw_text),
            )
        return ProviderError(
            "PROVIDER_ERROR",
            message or "AI 服务返回错误",
            http_status=502,
            retryable=True,
            latency_ms=latency,
            raw_response_text=_safe_raw(raw_text),
        )


def _completion_text(completion: Any) -> str:
    choices = getattr(completion, "choices", None)
    if not choices:
        raise ValueError("provider returned no choices")
    text = getattr(getattr(choices[0], "message", None), "content", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("provider returned empty text")
    return text.strip()


def _validate_output(raw_text: str) -> AIMessageOutput:
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("provider result must be a JSON object")
    return AIMessageOutput.model_validate(payload)


def _invalid_output(
    exc: Exception, started: float, raw_text: str | None
) -> ProviderError:
    return ProviderError(
        "INVALID_AI_OUTPUT",
        "AI 返回内容不是符合约定的 JSON",
        http_status=502,
        retryable=True,
        latency_ms=_elapsed_ms(started),
        raw_response_text=_safe_raw(raw_text),
    )


def _json_mode_unsupported(exc: BadRequestError) -> bool:
    text = str(exc).casefold()
    return "response_format" in text or "json mode" in text or "json_object" in text


def _looks_like_model_not_found(exc: Exception) -> bool:
    text = str(exc).casefold()
    return "model" in text and any(token in text for token in ("not found", "does not exist"))


def _sanitize_error(message: str, api_key: str) -> str:
    clean = message.replace(api_key, "***") if api_key else message
    return " ".join(clean.split())[:512]


def _safe_raw(raw_text: str | None) -> str | None:
    return raw_text[:_MAX_RAW_TEXT] if raw_text else None


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


