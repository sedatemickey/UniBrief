"""Phase 3 integration tests for advanced objects, statistics, and maintenance scans."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.ai import ProviderResult
from app.core.config import Settings
from app.core.security import USER_CSRF_COOKIE, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import (
    AIAnalysis,
    Category,
    Channel,
    Event,
    EventReminder,
    InformationCategory,
    InformationItem,
    InformationTag,
    Message,
    MessageInformation,
    Platform,
    Sender,
    Tag,
    User,
)
from app.schemas.ai import AIMessageOutput
from app.services import ai_service, task_service


class AutoProvider:
    """Test-only SDK boundary for automatic analysis."""

    def __init__(self, outcomes: list[dict[str, Any]]) -> None:
        self.outcomes = deque(outcomes)

    async def analyze(self, **_kwargs: Any) -> ProviderResult[AIMessageOutput]:
        """Return one strict queued output."""

        value = AIMessageOutput.model_validate(self.outcomes.popleft())
        raw = json.dumps(value.model_dump(mode="json"))
        return ProviderResult(value=value, raw_response_text=raw, latency_ms=5)


def _provision() -> tuple[TestClient, int, int]:
    with SessionLocal() as db:
        platform = Platform(name="QQ", type="IM")
        user_a = User(
            username="stats_a",
            display_name="统计用户 A",
            password_hash=hash_password("ExamplePass123"),
        )
        user_b = User(
            username="stats_b",
            display_name="统计用户 B",
            password_hash=hash_password("ExamplePass123"),
        )
        db.add_all([platform, user_a, user_b])
        db.flush()
        for user, suffix in ((user_a, "a"), (user_b, "b")):
            db.add_all(
                [
                    Channel(
                        user_id=user.id,
                        platform_id=platform.id,
                        external_id=f"group-{suffix}",
                        name=f"课程群 {suffix.upper()}",
                        channel_type="GROUP",
                    ),
                    Sender(
                        user_id=user.id,
                        platform_id=platform.id,
                        external_id=f"teacher-{suffix}",
                        display_name="张老师",
                        source_type="TEACHER",
                    ),
                ]
            )
        db.commit()
        user_a_id, user_b_id = user_a.id, user_b.id
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "stats_a", "password": "ExamplePass123"},
    )
    assert response.status_code == 200
    assert client.cookies.get(USER_CSRF_COOKIE)
    return client, user_a_id, user_b_id


def _add_message(
    db: Any,
    *,
    user_id: int,
    external_id: str,
    sent_at: datetime,
    status: str = "PENDING",
    ingested_at: datetime | None = None,
    processing_started_at: datetime | None = None,
) -> Message:
    channel = db.scalar(select(Channel).where(Channel.user_id == user_id))
    sender = db.scalar(select(Sender).where(Sender.user_id == user_id))
    message = Message(
        user_id=user_id,
        channel_id=channel.id,
        sender_id=sender.id,
        external_id=external_id,
        content="合成统计消息",
        sent_at=sent_at,
        ingested_at=ingested_at or sent_at,
        process_status=status,
        processing_started_at=processing_started_at,
    )
    db.add(message)
    db.flush()
    return message


def _add_information(
    db: Any,
    *,
    user_id: int,
    title: str,
    created_at: datetime,
    status: str = "ACTIVE",
) -> InformationItem:
    information = InformationItem(
        user_id=user_id,
        title=title,
        summary="合成摘要",
        source_type="TEACHER",
        importance=4,
        confidence=Decimal("0.900"),
        status=status,
        version=1,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(information)
    db.flush()
    return information


def test_statistics_use_procedure_views_trigger_half_open_ranges_and_isolation() -> None:
    client, user_a_id, user_b_id = _provision()
    start = datetime(2026, 9, 1, 0, 0)
    end = datetime(2026, 9, 2, 0, 0)
    with SessionLocal() as db:
        message_a1 = _add_message(
            db, user_id=user_a_id, external_id="a-1", sent_at=start
        )
        _add_message(
            db,
            user_id=user_a_id,
            external_id="a-2",
            sent_at=datetime(2026, 9, 1, 12, 0),
        )
        _add_message(db, user_id=user_a_id, external_id="a-end", sent_at=end)
        message_b = _add_message(
            db,
            user_id=user_b_id,
            external_id="b-1",
            sent_at=datetime(2026, 9, 1, 10, 0),
        )
        active = _add_information(
            db,
            user_id=user_a_id,
            title="数据库作业",
            created_at=datetime(2026, 9, 1, 1, 0),
        )
        archived = _add_information(
            db,
            user_id=user_a_id,
            title="历史作业",
            created_at=datetime(2026, 9, 1, 2, 0),
            status="ARCHIVED",
        )
        foreign = _add_information(
            db,
            user_id=user_b_id,
            title="其他用户事项",
            created_at=datetime(2026, 9, 1, 1, 0),
        )
        db.add_all(
            [
                MessageInformation(
                    user_id=user_a_id,
                    message_id=message_a1.id,
                    information_id=active.id,
                    relation_type="CREATE",
                ),
                MessageInformation(
                    user_id=user_b_id,
                    message_id=message_b.id,
                    information_id=foreign.id,
                    relation_type="CREATE",
                ),
            ]
        )
        category = db.scalar(select(Category).where(Category.name == "作业"))
        tag = Tag(user_id=user_a_id, name="数据库")
        db.add(tag)
        db.flush()
        db.add_all(
            [
                InformationCategory(information_id=active.id, category_id=category.id),
                InformationCategory(information_id=archived.id, category_id=category.id),
                InformationTag(
                    user_id=user_a_id,
                    information_id=active.id,
                    tag_id=tag.id,
                ),
            ]
        )
        shanghai = ZoneInfo("Asia/Shanghai")
        tomorrow = datetime.now(shanghai).date() + timedelta(days=1)
        event_start = datetime.combine(
            tomorrow, time(9, 0), tzinfo=shanghai
        ).astimezone(UTC)
        event = Event(
            information_id=active.id,
            start_at=event_start.replace(tzinfo=None),
            deadline=(event_start + timedelta(hours=9)).replace(tzinfo=None),
            event_status="UPCOMING",
        )
        db.add(event)
        db.flush()
        db.add(
            EventReminder(
                event_id=event.id,
                remind_at=datetime(2026, 9, 1, 10, 0),
                reminder_status="DUE",
                is_custom_time=False,
            )
        )
        db.commit()
        active_id = active.id

    query = "start=2026-09-01T00:00:00Z&end=2026-09-02T00:00:00Z"
    channels = client.get(f"/api/v1/statistics/channels?{query}")
    assert channels.status_code == 200
    assert channels.json() == [
        {
            "channel_id": 1,
            "channel_name": "课程群 A",
            "platform_id": 1,
            "platform_name": "QQ",
            "message_count": 2,
            "effective_message_count": 1,
            "effectiveness_rate": 0.5,
        }
    ]
    overview = client.get(f"/api/v1/statistics/overview?{query}")
    assert overview.status_code == 200
    assert overview.json() == {
        "message_total": 2,
        "information_active_total": 1,
        "event_upcoming_total": 0,
        "reminder_due_total": 1,
    }
    categories = client.get(f"/api/v1/statistics/categories?{query}")
    assert categories.status_code == 200
    assert categories.json()[0]["information_count"] == 1
    archived_categories = client.get(
        f"/api/v1/statistics/categories?{query}&include_archived=true"
    )
    assert archived_categories.json()[0]["information_count"] == 2
    tags = client.get(f"/api/v1/statistics/tags?{query}&limit=10")
    assert tags.status_code == 200
    assert tags.json() == [
        {"tag_id": 1, "tag_name": "数据库", "usage_count": 1}
    ]
    upcoming = client.get("/api/v1/statistics/upcoming-events?days=7")
    assert upcoming.status_code == 200
    assert upcoming.json()["total"] == 1
    assert upcoming.json()["by_date"][1] == {"date": tomorrow.isoformat(), "count": 1}

    with SessionLocal() as db:
        objects = db.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM information_schema.views
                     WHERE table_schema=DATABASE() AND table_name LIKE 'v_%') AS view_count,
                    (SELECT COUNT(*) FROM information_schema.triggers
                     WHERE trigger_schema=DATABASE()
                       AND trigger_name='trg_information_item_set_updated_at') AS trigger_count,
                    (SELECT COUNT(*) FROM information_schema.routines
                     WHERE routine_schema=DATABASE()
                       AND routine_name='sp_channel_statistics'
                       AND routine_type='PROCEDURE') AS procedure_count
                """
            )
        ).mappings().one()
        assert objects["view_count"] >= 4
        assert objects["trigger_count"] == 1
        assert objects["procedure_count"] == 1
        channel_view = db.execute(
            text(
                "SELECT message_count, effective_message_count, effectiveness_rate "
                "FROM v_channel_effectiveness WHERE user_id=:user_id"
            ),
            {"user_id": user_a_id},
        ).mappings().one()
        assert channel_view["message_count"] == 3
        assert channel_view["effective_message_count"] == 1
        assert float(channel_view["effectiveness_rate"]) == 0.3333
        category_view = db.execute(
            text(
                "SELECT information_count FROM v_category_statistics "
                "WHERE user_id=:user_id AND category_name='作业'"
            ),
            {"user_id": user_a_id},
        ).scalar_one()
        assert category_view == 2
        tag_view = db.execute(
            text(
                "SELECT usage_count FROM v_tag_popularity "
                "WHERE user_id=:user_id AND tag_name='数据库'"
            ),
            {"user_id": user_a_id},
        ).scalar_one()
        assert tag_view == 1
        db.execute(
            text(
                "UPDATE information_item SET updated_at='2026-01-01 00:00:00' WHERE id=:id"
            ),
            {"id": active_id},
        )
        db.execute(
            text("UPDATE information_item SET title='触发器更新' WHERE id=:id"),
            {"id": active_id},
        )
        updated_at = db.scalar(
            select(InformationItem.updated_at).where(InformationItem.id == active_id)
        )
        assert updated_at > datetime(2026, 1, 1)


def test_event_reminder_scan_and_stale_recovery_are_idempotent() -> None:
    _client, user_id, _other_user_id = _provision()
    now = datetime(2026, 9, 1, 12, 0)
    with SessionLocal() as db:
        information = [
            _add_information(
                db,
                user_id=user_id,
                title=f"事项 {index}",
                created_at=datetime(2026, 9, 1, 1, index),
            )
            for index in range(4)
        ]
        events = [
            Event(
                information_id=information[0].id,
                start_at=now - timedelta(hours=1),
                deadline=now + timedelta(hours=2),
                event_status="UPCOMING",
            ),
            Event(
                information_id=information[1].id,
                start_at=now - timedelta(days=1),
                deadline=now,
                event_status="ONGOING",
            ),
            Event(
                information_id=information[2].id,
                start_at=now - timedelta(days=1),
                deadline=now + timedelta(days=1),
                event_status="COMPLETED",
            ),
            Event(
                information_id=information[3].id,
                start_at=now + timedelta(hours=1),
                deadline=now + timedelta(days=1),
                event_status="UPCOMING",
            ),
        ]
        db.add_all(events)
        db.flush()
        reminders = [
            EventReminder(
                event_id=events[index].id,
                remind_at=now - timedelta(minutes=1),
                reminder_status="PENDING",
                is_custom_time=False,
            )
            for index in (1, 2, 3)
        ]
        db.add_all(reminders)
        stale = _add_message(
            db,
            user_id=user_id,
            external_id="stale",
            sent_at=now - timedelta(hours=1),
            status="PROCESSING",
            processing_started_at=now - timedelta(minutes=11),
        )
        db.commit()
        event_ids = [event.id for event in events]
        reminder_ids = [reminder.id for reminder in reminders]
        stale_id = stale.id

    first = task_service.run_event_reminder_scan(now)
    assert first == {
        "events_expired": 1,
        "events_ongoing": 1,
        "reminders_disabled": 2,
        "reminders_due": 1,
    }
    second = task_service.run_event_reminder_scan(now)
    assert second == {
        "events_expired": 0,
        "events_ongoing": 0,
        "reminders_disabled": 0,
        "reminders_due": 0,
    }
    recovered = task_service.recover_stale_messages(now)
    assert recovered == [stale_id]
    assert task_service.recover_stale_messages(now) == []
    with SessionLocal() as db:
        assert [db.get(Event, event_id).event_status for event_id in event_ids] == [
            "ONGOING",
            "EXPIRED",
            "COMPLETED",
            "UPCOMING",
        ]
        assert [
            db.get(EventReminder, reminder_id).reminder_status
            for reminder_id in reminder_ids
        ] == ["DISABLED", "DISABLED", "DUE"]
        stale = db.get(Message, stale_id)
        analysis = db.scalar(select(AIAnalysis).where(AIAnalysis.message_id == stale_id))
        assert stale.process_status == "FAILED"
        assert analysis and analysis.error_code == "PROCESSING_STALE"


def test_auto_analysis_uses_same_user_channel_threshold_and_atomic_claim(
    monkeypatch: Any,
) -> None:
    _client, user_id, _other_user_id = _provision()
    now = datetime(2026, 9, 1, 12, 0)
    with SessionLocal() as db:
        first = _add_message(
            db,
            user_id=user_id,
            external_id="auto-1",
            sent_at=now,
            ingested_at=now,
        )
        second = _add_message(
            db,
            user_id=user_id,
            external_id="auto-2",
            sent_at=now,
            ingested_at=now,
        )
        db.commit()
        ids = [first.id, second.id]
    settings = Settings(
        ai_api_key="test-key",
        ai_default_model="test-model",
        ai_batch_size_threshold=2,
        ai_batch_max_wait_seconds=300,
    )
    provider = AutoProvider(
        [
            {"useful": False, "items": []},
            {"useful": False, "items": []},
        ]
    )
    monkeypatch.setattr(task_service, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_service, "provider", lambda: provider)
    result = asyncio.run(task_service.run_auto_analysis_scan(now))
    assert result == {"recovered": 0, "groups": 1, "messages": 2, "skipped": False}
    with SessionLocal() as db:
        assert [db.get(Message, message_id).process_status for message_id in ids] == [
            "IGNORED",
            "IGNORED",
        ]
        assert len(
            list(db.scalars(select(AIAnalysis).where(AIAnalysis.message_id.in_(ids))))
        ) == 2

