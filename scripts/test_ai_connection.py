"""Perform one real OpenAI-compatible connectivity test without printing the API Key."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.ai import OpenAICompatibleProvider, ProviderError  # noqa: E402
from app.core.config import get_settings  # noqa: E402


async def _run() -> int:
    """Print a non-secret machine-readable connection result."""

    settings = get_settings()
    model = settings.ai_default_model.strip()
    public = {
        "base_url": settings.ai_base_url,
        "model": model or None,
    }
    if not settings.ai_api_key.strip():
        print(
            json.dumps(
                {
                    **public,
                    "ok": False,
                    "error_code": "AUTH_ERROR",
                    "message": "AI_API_KEY is not configured; integration test was not run.",
                },
                ensure_ascii=False,
            )
        )
        return 2
    if not model:
        print(
            json.dumps(
                {
                    **public,
                    "ok": False,
                    "error_code": "AI_MODEL_REQUIRED",
                    "message": "AI_DEFAULT_MODEL is not configured; integration test was not run.",
                },
                ensure_ascii=False,
            )
        )
        return 2
    try:
        latency_ms = await OpenAICompatibleProvider(settings).test_connection(model)
    except ProviderError as exc:
        print(
            json.dumps(
                {
                    **public,
                    "ok": False,
                    "latency_ms": exc.latency_ms,
                    "error_code": exc.code,
                    "message": exc.message,
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(
        json.dumps(
            {
                **public,
                "ok": True,
                "latency_ms": latency_ms,
                "message": "connection succeeded",
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    """Run the real integration check once."""

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
