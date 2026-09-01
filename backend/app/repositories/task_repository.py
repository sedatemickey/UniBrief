"""Database operations for idempotent single-process maintenance scans."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.enums import (
    AnalysisStatus,
    EventStatus,
    MessageStatus,
    ReminderStatus,
    UserStatus,
)
from app.models import AIAnalysis, Event, EventReminder, Message, User


def maintain_events_and_reminders(db: Session, now: datetime) -> dict[str, int]:
    """Advance Event and Reminder states with repeatable conditional updates."""

    expired = db.execute(
        update(Event)
        .where(
            Event.event_status.in_([EventStatus.UPCOMING.value, EventStatus.ONGOING.value]),
            Event.deadline.is_not(None),
            Event.deadline <= now,
        )
        .values(event_status=EventStatus.EXPIRED.value, updated_at=func.now())
    ).rowcount
    ongoing = db.execute(
        update(Event)
        .where(
            Event.event_status == EventStatus.UPCOMING.value,
            Event.start_at.is_not(None),
            Event.start_at <= now,
            (Event.deadline.is_(None) | (Event.deadline > now)),
        )
        .values(event_status=EventStatus.ONGOING.value, updated_at=func.now())
    ).rowcount
    terminal_event_ids = select(Event.id).where(
        Event.event_status.in_(
            [EventStatus.COMPLETED.value, EventStatus.CANCELLED.value, EventStatus.EXPIRED.value]
        )
    )
    disabled = db.execute(
        update(EventReminder)
        .where(
            EventReminder.reminder_status == ReminderStatus.PENDING.value,
            EventReminder.event_id.in_(terminal_event_ids),
        )
        .values(reminder_status=ReminderStatus.DISABLED.value, updated_at=func.now())
    ).rowcount
    active_event_ids = select(Event.id).where(
        Event.event_status.in_([EventStatus.UPCOMING.value, EventStatus.ONGOING.value])
    )
    due = db.execute(
        update(EventReminder)
        .where(
            EventReminder.reminder_status == ReminderStatus.PENDING.value,
            EventReminder.remind_at <= now,
            EventReminder.event_id.in_(active_event_ids),
        )
        .values(
            reminder_status=ReminderStatus.DUE.value,
            triggered_at=now,
            updated_at=func.now(),
        )
    ).rowcount
    return {
        "events_expired": expired,
        "events_ongoing": ongoing,
        "reminders_disabled": disabled,
        "reminders_due": due,
    }


def recover_stale_processing(
    db: Session,
    *,
    cutoff: datetime,
    now: datetime,
) -> list[int]:
    """Mark stale PROCESSING Messages FAILED and persist one recovery audit row."""

    stale_ids = list(
        db.scalars(
            select(Message.id).where(
                Message.process_status == MessageStatus.PROCESSING.value,
                Message.processing_started_at.is_not(None),
                Message.processing_started_at <= cutoff,
            )
        )
    )
    recovered: list[int] = []
    for message_id in stale_ids:
        claimed = db.execute(
            update(Message)
            .where(
                Message.id == message_id,
                Message.process_status == MessageStatus.PROCESSING.value,
                Message.processing_started_at <= cutoff,
            )
            .values(process_status=MessageStatus.FAILED.value, processing_started_at=None)
        )
        if claimed.rowcount != 1:
            continue
        recovered.append(message_id)
        db.add(
            AIAnalysis(
                message_id=message_id,
                model_name="system-recovery",
                status=AnalysisStatus.FAILED.value,
                error_code="PROCESSING_STALE",
                error_message="处理超时，已恢复为可重试状态",
                analyzed_at=now,
            )
        )
    return recovered


def eligible_pending_groups(
    db: Session,
    *,
    size_threshold: int,
    wait_cutoff: datetime,
) -> list[tuple[int, int, int]]:
    """Find active-user/channel groups that reached size or wait thresholds."""

    rows = db.execute(
        select(
            Message.user_id,
            Message.channel_id,
            func.count(Message.id).label("message_count"),
            func.min(Message.ingested_at).label("oldest"),
        )
        .join(User, User.id == Message.user_id)
        .where(
            User.status == UserStatus.ACTIVE.value,
            Message.process_status == MessageStatus.PENDING.value,
        )
        .group_by(Message.user_id, Message.channel_id)
        .having(
            (func.count(Message.id) >= size_threshold)
            | (func.min(Message.ingested_at) <= wait_cutoff)
        )
        .order_by(func.min(Message.ingested_at), Message.user_id, Message.channel_id)
    ).all()
    return [(row.user_id, row.channel_id, row.message_count) for row in rows]


def pending_message_ids(
    db: Session,
    *,
    user_id: int,
    channel_id: int,
    limit: int,
) -> list[int]:
    """Return oldest PENDING IDs for one user/channel group."""

    return list(
        db.scalars(
            select(Message.id)
            .where(
                Message.user_id == user_id,
                Message.channel_id == channel_id,
                Message.process_status == MessageStatus.PENDING.value,
            )
            .order_by(Message.ingested_at, Message.id)
            .limit(limit)
        )
    )

