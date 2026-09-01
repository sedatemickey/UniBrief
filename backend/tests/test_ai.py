"""Phase 2 tests for provider contracts and transactionally applied AI results."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai import ProviderError, ProviderResult
from app.core.enums import MessageStatus
from app.core.security import USER_CSRF_COOKIE, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import (
    AIAnalysis,
    Channel,
    Event,
    EventReminder,
    InformationItem,
    Message,
    MessageInformation,
    Platform,
    Sender,
    User,
)
from app.schemas.ai import AIMessageOutput
from app.services import ai_service


class StubProvider:
    """Test-only queued SDK substitute; it is never runtime-selectable."""

    def __init__(self, outcomes: list[Any] | None = None) -> None:
        self.outcomes = deque(outcomes or [])
        self.calls = 0

    async def analyze(self, **_kwargs: Any) -> ProviderResult[AIMessageOutput]:
        """Return or raise the next deterministic test outcome."""

        self.calls += 1
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        value = AIMessageOutput.model_validate(outcome)
        raw = json.dumps(value.model_dump(mode="json"), ensure_ascii=False)
        return ProviderResult(value=value, raw_response_text=raw, latency_ms=12)

    async def list_models(self) -> list[str]:
        """Return a deterministic unsorted list for API sorting tests."""

        return ["model-b", "model-a"]

    async def test_connection(self, _model: str) -> int:
        """Return deterministic latency without making a real request."""

        return 23


def _provision() -> tuple[TestClient, str, int]:
    with SessionLocal() as db:
        user = User(
            username="ai_user",
            display_name="AI 测试用户",
            password_hash=hash_password("ExamplePass123"),
        )
        platform = Platform(name="QQ", type="IM")
        db.add_all([user, platform])
        db.flush()
        channel = Channel(
            user_id=user.id,
            platform_id=platform.id,
            external_id="group-ai",
            name="AI 测试群",
            channel_type="GROUP",
        )
        sender = Sender(
            user_id=user.id,
            platform_id=platform.id,
            external_id="teacher-ai",
            display_name="张老师",
            source_type="TEACHER",
        )
        db.add_all([channel, sender])
        db.commit()
        user_id = user.id
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "ai_user", "password": "ExamplePass123"},
    )
    assert login.status_code == 200
    csrf = client.cookies.get(USER_CSRF_COOKIE)
    assert csrf
    return client, csrf, user_id


def _message(user_id: int, external_id: str, content: str) -> int:
    with SessionLocal() as db:
        channel = db.scalar(select(Channel).where(Channel.user_id == user_id))
        sender = db.scalar(select(Sender).where(Sender.user_id == user_id))
        assert channel and sender
        message = Message(
            user_id=user_id,
            channel_id=channel.id,
            sender_id=sender.id,
            external_id=external_id,
            content=content,
            sent_at=datetime(2026, 9, 1, 1, 30),
            process_status=MessageStatus.PENDING.value,
        )
        db.add(message)
        db.commit()
        return message.id


def _create_result(*, deadline: str = "2026-09-10T18:00:00+08:00") -> dict[str, Any]:
    return {
        "useful": True,
        "items": [
            {
                "action": "create",
                "target_information_id": None,
                "relation_type": "CREATE",
                "title": "数据库课程设计提交",
                "summary": "课程设计初稿需要按时提交",
                "source_type": "TEACHER",
                "importance": 5,
                "confidence": 0.95,
                "categories": ["作业"],
                "tags": ["数据库", "课程设计"],
                "event": {
                    "start_at": None,
                    "deadline": deadline,
                    "status": "UPCOMING",
                },
            }
        ],
    }


def _target_result(information_id: int, *, action: str, deadline: str) -> dict[str, Any]:
    relation = {"link": "SUPPORT", "update": "UPDATE", "correct": "CORRECTION"}[action]
    return {
        "useful": True,
        "items": [
            {
                "action": action,
                "target_information_id": information_id,
                "relation_type": relation,
                "title": "数据库课程设计提交（更新）",
                "summary": "截止时间已更新",
                "source_type": "TEACHER",
                "importance": 5,
                "confidence": 0.98,
                "categories": ["作业"],
                "tags": ["数据库", "变更"],
                "event": {
                    "start_at": None,
                    "deadline": deadline,
                    "status": "UPCOMING",
                },
            }
        ],
    }


def test_ai_config_models_and_test_never_expose_key(monkeypatch: pytest.MonkeyPatch) -> None:
    client, csrf, _user_id = _provision()
    stub = StubProvider()
    monkeypatch.setattr(ai_service, "provider", lambda: stub)

    config = client.get("/api/v1/ai/config")
    assert config.status_code == 200
    assert "api_key" not in config.json()
    assert set(config.json()) == {
        "base_url",
        "default_model",
        "timeout_seconds",
        "max_retries",
        "has_api_key",
    }
    models = client.get("/api/v1/ai/models")
    assert models.status_code == 200
    assert [item["id"] for item in models.json()["models"]] == ["model-a", "model-b"]
    tested = client.post(
        "/api/v1/ai/test",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert tested.status_code == 200
    assert tested.json()["latency_ms"] == 23


def test_models_unsupported_returns_manual_input_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _csrf, _user_id = _provision()
    stub = StubProvider()

    async def unsupported() -> list[str]:
        raise ProviderError(
            "MODEL_LIST_UNSUPPORTED",
            "请手工输入模型 ID",
            http_status=200,
            retryable=False,
        )

    stub.list_models = unsupported  # type: ignore[method-assign]
    monkeypatch.setattr(ai_service, "provider", lambda: stub)
    response = client.get("/api/v1/ai/models")
    assert response.status_code == 200
    assert response.json() == {
        "supports_listing": False,
        "models": [],
        "error_code": "MODEL_LIST_UNSUPPORTED",
        "message": "请手工输入模型 ID",
    }


def test_useful_false_is_ignored_without_information(monkeypatch: pytest.MonkeyPatch) -> None:
    client, csrf, user_id = _provision()
    message_id = _message(user_id, "chat-1", "收到，谢谢老师")
    stub = StubProvider([{"useful": False, "items": []}])
    monkeypatch.setattr(ai_service, "provider", lambda: stub)

    response = client.post(
        f"/api/v1/messages/{message_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a", "mode": "retry"},
    )
    assert response.status_code == 200
    assert response.json()["process_status"] == "IGNORED"
    with SessionLocal() as db:
        assert db.scalar(select(func.count(InformationItem.id))) == 0
        analysis = db.scalar(select(AIAnalysis).where(AIAnalysis.message_id == message_id))
        assert analysis and analysis.status == "SUCCEEDED" and analysis.useful is False


def test_create_event_default_reminder_and_compare_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, csrf, user_id = _provision()
    message_id = _message(user_id, "notice-1", "数据库课程设计 9 月 10 日提交")
    stub = StubProvider([_create_result(), {"useful": False, "items": []}])
    monkeypatch.setattr(ai_service, "provider", lambda: stub)

    created = client.post(
        f"/api/v1/messages/{message_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert created.status_code == 200
    information_id = created.json()["information_ids"][0]
    with SessionLocal() as db:
        event = db.scalar(select(Event).where(Event.information_id == information_id))
        assert event and event.deadline == datetime(2026, 9, 10, 10, 0)
        reminder = db.scalar(select(EventReminder).where(EventReminder.event_id == event.id))
        assert reminder and reminder.remind_at == datetime(2026, 9, 9, 10, 0)
        assert reminder.reminder_status == "PENDING"
        before_version = db.get(InformationItem, information_id).version

    compared = client.post(
        f"/api/v1/messages/{message_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-b", "mode": "compare"},
    )
    assert compared.status_code == 200
    assert compared.json()["business_applied"] is False
    assert compared.json()["process_status"] == "PROCESSED"
    with SessionLocal() as db:
        assert db.get(InformationItem, information_id).version == before_version
        assert db.scalar(select(func.count(AIAnalysis.id))) == 2


def test_update_uses_optimistic_version_and_recalculates_default_reminder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, csrf, user_id = _provision()
    first_id = _message(user_id, "notice-1", "数据库课程设计 9 月 10 日提交")
    first_stub = StubProvider([_create_result()])
    monkeypatch.setattr(ai_service, "provider", lambda: first_stub)
    first = client.post(
        f"/api/v1/messages/{first_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    information_id = first.json()["information_ids"][0]

    second_id = _message(user_id, "notice-2", "数据库课程设计截止时间改为 9 月 12 日")
    update_stub = StubProvider(
        [_target_result(information_id, action="update", deadline="2026-09-12T18:00:00+08:00")]
    )
    monkeypatch.setattr(ai_service, "provider", lambda: update_stub)
    updated = client.post(
        f"/api/v1/messages/{second_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert updated.status_code == 200
    with SessionLocal() as db:
        information = db.get(InformationItem, information_id)
        assert information and information.version == 2
        relation = db.get(MessageInformation, (second_id, information_id))
        assert relation and relation.relation_type == "UPDATE"
        event = db.scalar(select(Event).where(Event.information_id == information_id))
        reminder = db.scalar(select(EventReminder).where(EventReminder.event_id == event.id))
        assert event.deadline == datetime(2026, 9, 12, 10, 0)
        assert reminder.remind_at == datetime(2026, 9, 11, 10, 0)


@pytest.mark.parametrize(
    ("error", "http_status"),
    [
        (ProviderError("AUTH_ERROR", "auth", http_status=502, retryable=False), 502),
        (ProviderError("MODEL_NOT_FOUND", "model", http_status=502, retryable=False), 502),
        (ProviderError("RATE_LIMITED", "rate", http_status=429, retryable=True), 429),
        (ProviderError("TIMEOUT", "timeout", http_status=504, retryable=True), 504),
        (ProviderError("NETWORK_ERROR", "network", http_status=502, retryable=True), 502),
        (ProviderError("INVALID_AI_OUTPUT", "invalid", http_status=502, retryable=True), 502),
    ],
)
def test_provider_failures_are_persisted_and_retryable(
    monkeypatch: pytest.MonkeyPatch,
    error: ProviderError,
    http_status: int,
) -> None:
    client, csrf, user_id = _provision()
    message_id = _message(user_id, "failure-1", "需要分析的通知")
    monkeypatch.setattr(ai_service, "provider", lambda: StubProvider([error]))
    response = client.post(
        f"/api/v1/messages/{message_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert response.status_code == http_status
    assert response.json()["error"]["code"] == error.code
    with SessionLocal() as db:
        message = db.get(Message, message_id)
        analysis = db.scalar(select(AIAnalysis).where(AIAnalysis.message_id == message_id))
        assert message and message.process_status == "FAILED"
        assert message.processing_started_at is None
        assert analysis and analysis.status == "FAILED" and analysis.error_code == error.code


def test_batch_allows_partial_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client, csrf, user_id = _provision()
    first = _message(user_id, "batch-1", "普通闲聊")
    second = _message(user_id, "batch-2", "需要分析的通知")
    stub = StubProvider(
        [
            {"useful": False, "items": []},
            ProviderError("TIMEOUT", "timeout", http_status=504, retryable=True),
        ]
    )
    monkeypatch.setattr(ai_service, "provider", lambda: stub)
    response = client.post(
        "/api/v1/messages/analyze-batch",
        headers={"X-CSRF-Token": csrf},
        json={"message_ids": [first, second], "model": "model-a", "mode": "retry"},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["status"] == "IGNORED" and results[0]["error"] is None
    assert results[1]["status"] == "FAILED"
    assert results[1]["error"]["code"] == "TIMEOUT"



def test_link_and_correct_apply_documented_relation_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, csrf, user_id = _provision()
    first_id = _message(user_id, "semantics-1", "数据库课程设计 9 月 10 日提交")
    monkeypatch.setattr(ai_service, "provider", lambda: StubProvider([_create_result()]))
    created = client.post(
        f"/api/v1/messages/{first_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    information_id = created.json()["information_ids"][0]

    link_id = _message(user_id, "semantics-2", "数据库课程设计提交要求确认收到")
    monkeypatch.setattr(
        ai_service,
        "provider",
        lambda: StubProvider(
            [
                _target_result(
                    information_id,
                    action="link",
                    deadline="2026-09-20T18:00:00+08:00",
                )
            ]
        ),
    )
    linked = client.post(
        f"/api/v1/messages/{link_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert linked.status_code == 200
    with SessionLocal() as db:
        information = db.get(InformationItem, information_id)
        relation = db.get(MessageInformation, (link_id, information_id))
        event = db.scalar(select(Event).where(Event.information_id == information_id))
        assert information and information.version == 1
        assert relation and relation.relation_type == "SUPPORT"
        assert event and event.deadline == datetime(2026, 9, 10, 10, 0)

    correct_id = _message(user_id, "semantics-3", "更正：数据库课程设计 9 月 11 日提交")
    monkeypatch.setattr(
        ai_service,
        "provider",
        lambda: StubProvider(
            [
                _target_result(
                    information_id,
                    action="correct",
                    deadline="2026-09-11T18:00:00+08:00",
                )
            ]
        ),
    )
    corrected = client.post(
        f"/api/v1/messages/{correct_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert corrected.status_code == 200
    with SessionLocal() as db:
        information = db.get(InformationItem, information_id)
        relation = db.get(MessageInformation, (correct_id, information_id))
        assert information and information.version == 2
        assert relation and relation.relation_type == "CORRECTION"


def test_concurrent_update_reloads_once_then_fails_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import analysis_repository

    client, csrf, user_id = _provision()
    first_id = _message(user_id, "conflict-1", "数据库课程设计 9 月 10 日提交")
    monkeypatch.setattr(ai_service, "provider", lambda: StubProvider([_create_result()]))
    created = client.post(
        f"/api/v1/messages/{first_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    information_id = created.json()["information_ids"][0]
    conflict_id = _message(user_id, "conflict-2", "数据库课程设计截止时间更新")
    update_result = _target_result(
        information_id,
        action="update",
        deadline="2026-09-12T18:00:00+08:00",
    )
    stub = StubProvider([update_result, update_result])
    monkeypatch.setattr(ai_service, "provider", lambda: stub)
    monkeypatch.setattr(
        analysis_repository,
        "optimistic_update_information",
        lambda *_args, **_kwargs: False,
    )

    response = client.post(
        f"/api/v1/messages/{conflict_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONCURRENT_UPDATE"
    assert stub.calls == 2
    with SessionLocal() as db:
        information = db.get(InformationItem, information_id)
        message = db.get(Message, conflict_id)
        attempts = list(
            db.scalars(
                select(AIAnalysis)
                .where(AIAnalysis.message_id == conflict_id)
                .order_by(AIAnalysis.id)
            )
        )
        assert information and information.version == 1
        assert message and message.process_status == "FAILED"
        assert [item.error_code for item in attempts] == [
            "CONCURRENT_UPDATE",
            "CONCURRENT_UPDATE",
        ]


def test_deadline_updates_preserve_custom_and_disabled_reminders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, csrf, user_id = _provision()
    first_id = _message(user_id, "reminder-1", "数据库课程设计 9 月 10 日提交")
    monkeypatch.setattr(ai_service, "provider", lambda: StubProvider([_create_result()]))
    created = client.post(
        f"/api/v1/messages/{first_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    information_id = created.json()["information_ids"][0]
    custom_time = datetime(2026, 9, 8, 3, 0)
    with SessionLocal() as db:
        event = db.scalar(select(Event).where(Event.information_id == information_id))
        reminder = db.scalar(select(EventReminder).where(EventReminder.event_id == event.id))
        reminder.is_custom_time = True
        reminder.remind_at = custom_time
        db.commit()

    update_id = _message(user_id, "reminder-2", "数据库课程设计改为 9 月 12 日提交")
    monkeypatch.setattr(
        ai_service,
        "provider",
        lambda: StubProvider(
            [
                _target_result(
                    information_id,
                    action="update",
                    deadline="2026-09-12T18:00:00+08:00",
                )
            ]
        ),
    )
    response = client.post(
        f"/api/v1/messages/{update_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert response.status_code == 200
    with SessionLocal() as db:
        event = db.scalar(select(Event).where(Event.information_id == information_id))
        reminder = db.scalar(select(EventReminder).where(EventReminder.event_id == event.id))
        assert reminder.remind_at == custom_time
        reminder.is_custom_time = False
        reminder.reminder_status = "DISABLED"
        disabled_time = reminder.remind_at
        db.commit()

    correct_id = _message(user_id, "reminder-3", "更正：数据库课程设计 9 月 13 日提交")
    monkeypatch.setattr(
        ai_service,
        "provider",
        lambda: StubProvider(
            [
                _target_result(
                    information_id,
                    action="correct",
                    deadline="2026-09-13T18:00:00+08:00",
                )
            ]
        ),
    )
    response = client.post(
        f"/api/v1/messages/{correct_id}/analyze",
        headers={"X-CSRF-Token": csrf},
        json={"model": "model-a"},
    )
    assert response.status_code == 200
    with SessionLocal() as db:
        event = db.scalar(select(Event).where(Event.information_id == information_id))
        reminder = db.scalar(select(EventReminder).where(EventReminder.event_id == event.id))
        assert reminder.reminder_status == "DISABLED"
        assert reminder.remind_at == disabled_time
