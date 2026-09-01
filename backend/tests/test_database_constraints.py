"""MySQL integration tests for ownership and physical schema constraints."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, engine
from app.models import (
    Channel,
    InformationItem,
    InformationTag,
    Message,
    MessageInformation,
    Platform,
    Sender,
    Tag,
    User,
)
from app.services.setting_service import set_setting


def _create_cross_user_fixture() -> dict[str, int]:
    with SessionLocal() as db:
        user_a = User(
            username="constraint_a",
            display_name="A",
            password_hash="not-used-in-constraint-test",
        )
        user_b = User(
            username="constraint_b",
            display_name="B",
            password_hash="not-used-in-constraint-test",
        )
        platform = Platform(name="ConstraintPlatform", type="IM")
        db.add_all([user_a, user_b, platform])
        db.flush()
        channel_a = Channel(
            user_id=user_a.id,
            platform_id=platform.id,
            external_id="channel-a",
            name="A channel",
            channel_type="GROUP",
        )
        sender_a = Sender(
            user_id=user_a.id,
            platform_id=platform.id,
            external_id="sender-a",
            display_name="A sender",
        )
        db.add_all([channel_a, sender_a])
        db.flush()
        message_a = Message(
            user_id=user_a.id,
            channel_id=channel_a.id,
            sender_id=sender_a.id,
            external_id="message-a",
            content="evidence",
            sent_at=datetime(2026, 9, 1, 1, 0, 0),
        )
        info_a = InformationItem(
            user_id=user_a.id,
            title="A info",
            summary="A summary",
            source_type="TEACHER",
            importance=3,
            confidence=Decimal("0.800"),
        )
        info_b = InformationItem(
            user_id=user_b.id,
            title="B info",
            summary="B summary",
            source_type="TEACHER",
            importance=3,
            confidence=Decimal("0.800"),
        )
        tag_b = Tag(user_id=user_b.id, name="B tag")
        db.add_all([message_a, info_a, info_b, tag_b])
        db.commit()
        return {
            "user_a": user_a.id,
            "message_a": message_a.id,
            "info_a": info_a.id,
            "info_b": info_b.id,
            "tag_b": tag_b.id,
        }


def test_cross_user_association_rows_are_rejected_by_mysql() -> None:
    ids = _create_cross_user_fixture()
    with SessionLocal() as db:
        db.add(
            MessageInformation(
                user_id=ids["user_a"],
                message_id=ids["message_a"],
                information_id=ids["info_b"],
                relation_type="SUPPORT",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    with SessionLocal() as db:
        db.add(
            InformationTag(
                user_id=ids["user_a"],
                information_id=ids["info_a"],
                tag_id=ids["tag_b"],
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_physical_schema_has_required_tables_indexes_checks_and_uniques() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert len(tables) == 16
    assert {
        "user",
        "system_setting",
        "message",
        "information_item",
        "event",
        "event_reminder",
    }.issubset(tables)

    message_indexes = {item["name"] for item in inspector.get_indexes("message")}
    assert {
        "ix_message_user_channel_sent",
        "ix_message_user_sender_sent",
        "ix_message_status_processing",
        "uq_message_user_channel_external",
    }.issubset(message_indexes)
    reminder_indexes = {item["name"] for item in inspector.get_indexes("event_reminder")}
    assert "ix_reminder_status_remind_at" in reminder_indexes
    assert any(
        set(item["column_names"]) == {"event_id"}
        for item in inspector.get_unique_constraints("event_reminder")
    )
    assert any(
        set(item["column_names"]) == {"information_id"}
        for item in inspector.get_unique_constraints("event")
    )
    info_checks = {item["name"] for item in inspector.get_check_constraints("information_item")}
    assert "ck_information_item_confidence_range" in info_checks
    assert "ck_information_item_importance_range" in info_checks
    event_checks = {item["name"] for item in inspector.get_check_constraints("event")}
    assert "ck_event_time_present" in event_checks
    assert "ck_event_time_order" in event_checks


def test_setting_service_rejects_unregistered_keys() -> None:
    with SessionLocal() as db, pytest.raises(Exception) as exc_info:
        set_setting(db, "arbitrary_business_blob", "not allowed")
    assert getattr(exc_info.value, "code", None) == "VALIDATION_ERROR"
