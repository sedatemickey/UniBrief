"""Integration tests for Phase 4 Information, Event, and Reminder APIs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import USER_CSRF_COOKIE, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import (
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


def _provision() -> tuple[TestClient, str, int]:
    with SessionLocal() as db:
        platform = Platform(name="QQ", type="IM")
        user = User(
            username="ui_user",
            display_name="UI 测试用户",
            password_hash=hash_password("ExamplePass123"),
        )
        db.add_all([platform, user])
        db.flush()
        channel = Channel(
            user_id=user.id,
            platform_id=platform.id,
            external_id="ui-group",
            name="数据库课程群",
            channel_type="GROUP",
        )
        sender = Sender(
            user_id=user.id,
            platform_id=platform.id,
            external_id="ui-teacher",
            display_name="张老师",
            source_type="TEACHER",
        )
        db.add_all([channel, sender])
        db.flush()
        message = Message(
            user_id=user.id,
            channel_id=channel.id,
            sender_id=sender.id,
            external_id="ui-message",
            content="课程设计报告 9 月 10 日前提交",
            sent_at=datetime(2026, 9, 1, 1, 0),
            process_status="PROCESSED",
        )
        first = InformationItem(
            user_id=user.id,
            title="数据库课程设计提交",
            summary="提交课程设计报告",
            source_type="TEACHER",
            importance=5,
            confidence=Decimal("0.950"),
            created_at=datetime(2026, 9, 1, 2, 0),
            updated_at=datetime(2026, 9, 1, 2, 0),
        )
        second = InformationItem(
            user_id=user.id,
            title="英语四级报名",
            summary="英语四级考试报名开始",
            source_type="ADMIN",
            importance=3,
            confidence=Decimal("0.800"),
            created_at=datetime(2026, 9, 2, 2, 0),
            updated_at=datetime(2026, 9, 2, 2, 0),
        )
        db.add_all([message, first, second])
        db.flush()
        db.add(
            MessageInformation(
                user_id=user.id,
                message_id=message.id,
                information_id=first.id,
                relation_type="CREATE",
            )
        )
        homework = db.scalar(select(Category).where(Category.name == "作业"))
        exam = db.scalar(select(Category).where(Category.name == "考试"))
        db.add_all(
            [
                InformationCategory(information_id=first.id, category_id=homework.id),
                InformationCategory(information_id=second.id, category_id=exam.id),
                Event(
                    information_id=first.id,
                    start_at=datetime(2026, 9, 10, 1, 0),
                    deadline=datetime(2026, 9, 10, 10, 0),
                    event_status="UPCOMING",
                ),
            ]
        )
        tag = Tag(user_id=user.id, name="数据库")
        db.add(tag)
        db.flush()
        db.add(
            InformationTag(
                user_id=user.id,
                information_id=first.id,
                tag_id=tag.id,
            )
        )
        db.commit()
        user_id = user.id
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "ui_user", "password": "ExamplePass123"},
    )
    assert response.status_code == 200
    csrf = client.cookies.get(USER_CSRF_COOKIE)
    assert csrf
    return client, csrf, user_id


def test_information_combined_filters_detail_and_optimistic_patch() -> None:
    client, csrf, user_id = _provision()
    with SessionLocal() as db:
        first = db.scalar(select(InformationItem).where(InformationItem.user_id == user_id))
        homework = db.scalar(select(Category).where(Category.name == "作业"))
        tag = db.scalar(select(Tag).where(Tag.user_id == user_id))

    query = (
        f"category_ids={homework.id}&tag_ids={tag.id}&importance_min=4&status=ACTIVE"
        "&created_from=2026-09-01T00:00:00Z&created_to=2026-09-02T00:00:00Z"
        "&event_from=2026-09-10T00:00:00Z&event_to=2026-09-11T00:00:00Z"
        "&keyword=%E8%AF%BE%E7%A8%8B&page=1&page_size=20"
    )
    listed = client.get(f"/api/v1/information?{query}")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == first.id

    detail = client.get(f"/api/v1/information/{first.id}")
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["message_id"] == 1
    assert detail.json()["event"]["deadline"] == "2026-09-10T10:00:00Z"

    conflict = client.patch(
        f"/api/v1/information/{first.id}",
        headers={"X-CSRF-Token": csrf},
        json={"expected_version": first.version + 10, "title": "并发覆盖"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "VERSION_CONFLICT"

    patched = client.patch(
        f"/api/v1/information/{first.id}",
        headers={"X-CSRF-Token": csrf},
        json={
            "expected_version": first.version,
            "title": "数据库课程设计最终提交",
            "importance": 4,
            "category_ids": [homework.id],
            "tag_names": [],
        },
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == first.version + 1
    assert patched.json()["tags"] == []
    with SessionLocal() as db:
        persisted = db.get(InformationItem, first.id)
        persisted_tag = db.scalar(
            select(InformationTag).where(InformationTag.information_id == first.id)
        )
        assert persisted and persisted.version == 2
        assert persisted_tag is None


def test_event_overlap_patch_and_reminder_lifecycle() -> None:
    client, csrf, user_id = _provision()
    with SessionLocal() as db:
        information = db.scalar(select(InformationItem).where(InformationItem.user_id == user_id))
        event = db.scalar(select(Event).where(Event.information_id == information.id))
        db.add(
            EventReminder(
                event_id=event.id,
                remind_at=datetime(2026, 9, 9, 10, 0),
                reminder_status="PENDING",
                is_custom_time=False,
            )
        )
        db.commit()
        event_id = event.id

    # end boundary 10:00 is excluded; effective end is deadline=10:00.
    listed = client.get(
        "/api/v1/events?range_start=2026-09-10T00:00:00Z&range_end=2026-09-10T10:00:00Z"
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    listed = client.get(
        "/api/v1/events?range_start=2026-09-10T00:00:00Z&range_end=2026-09-10T10:00:01Z"
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    patched = client.patch(
        f"/api/v1/events/{event_id}",
        headers={"X-CSRF-Token": csrf},
        json={
            "expected_information_version": information.version,
            "start_at": "2026-09-11T01:00:00Z",
            "deadline": "2026-09-11T18:00:00Z",
            "event_status": "UPCOMING",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["start_at"] == "2026-09-11T01:00:00Z"
    assert patched.json()["information_version"] == information.version + 1
    with SessionLocal() as db:
        reminder = db.scalar(select(EventReminder).where(EventReminder.event_id == event_id))
        assert reminder.remind_at == datetime(2026, 9, 10, 18, 0)
        reminder_id = reminder.id

    customized = client.patch(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-CSRF-Token": csrf},
        json={"remind_at": "2026-09-01T00:00:00Z"},
    )
    assert customized.status_code == 200
    assert customized.json()["is_custom_time"] is True
    assert customized.json()["reminder_status"] == "DUE"
    read = client.post(
        f"/api/v1/reminders/{reminder_id}/read", headers={"X-CSRF-Token": csrf}
    )
    assert read.status_code == 200
    assert read.json()["reminder_status"] == "READ"
    disabled = client.patch(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-CSRF-Token": csrf},
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["reminder_status"] == "DISABLED"



def test_information_event_and_reminder_are_private_to_owner() -> None:
    owner, _csrf, owner_id = _provision()
    with SessionLocal() as db:
        information = db.scalar(select(InformationItem).where(InformationItem.user_id == owner_id))
        event = db.scalar(select(Event).where(Event.information_id == information.id))
        reminder = EventReminder(
            event_id=event.id,
            remind_at=datetime(2026, 9, 9, 10, 0),
            reminder_status="PENDING",
        )
        other = User(
            username="other_ui_user",
            display_name="其他用户",
            password_hash=hash_password("ExamplePass123"),
        )
        db.add_all([reminder, other])
        db.commit()
        event_id, reminder_id = event.id, reminder.id

    stranger = TestClient(app)
    assert stranger.post(
        "/api/v1/auth/login",
        json={"username": "other_ui_user", "password": "ExamplePass123"},
    ).status_code == 200
    assert stranger.get(f"/api/v1/information/{information.id}").status_code == 404
    assert stranger.get(f"/api/v1/events/{event_id}").status_code == 404
    stranger_csrf = stranger.cookies.get(USER_CSRF_COOKIE)
    assert stranger.patch(
        f"/api/v1/reminders/{reminder_id}",
        headers={"X-CSRF-Token": stranger_csrf},
        json={"enabled": False},
    ).status_code == 404
    assert stranger.get("/api/v1/events").json()["total"] == 0
    assert stranger.get("/api/v1/reminders").json()["total"] == 0

