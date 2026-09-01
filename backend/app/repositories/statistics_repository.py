"""Current-user statistical queries and stored-procedure access."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, select, text
from sqlalchemy.orm import Session

from app.core.enums import EventStatus, InformationStatus, ReminderStatus
from app.models import (
    Category,
    Event,
    EventReminder,
    InformationCategory,
    InformationItem,
    InformationTag,
    Message,
    Tag,
)


def overview(
    db: Session,
    *,
    user_id: int,
    start: datetime | None,
    end: datetime | None,
) -> dict[str, int]:
    """Count the four dashboard resources inside the authenticated user boundary."""

    message_filters = [Message.user_id == user_id]
    information_filters = [
        InformationItem.user_id == user_id,
        InformationItem.status.in_(
            [InformationStatus.ACTIVE.value, InformationStatus.UPDATED.value]
        ),
    ]
    event_filters = [
        InformationItem.user_id == user_id,
        Event.event_status.in_([EventStatus.UPCOMING.value, EventStatus.ONGOING.value]),
    ]
    reminder_filters = [
        InformationItem.user_id == user_id,
        EventReminder.reminder_status == ReminderStatus.DUE.value,
    ]
    if start is not None and end is not None:
        message_filters.extend([Message.sent_at >= start, Message.sent_at < end])
        information_filters.extend(
            [InformationItem.created_at >= start, InformationItem.created_at < end]
        )
        event_filters.append(_event_overlaps(start, end))
        reminder_filters.extend(
            [EventReminder.remind_at >= start, EventReminder.remind_at < end]
        )
    message_total = db.scalar(select(func.count(Message.id)).where(*message_filters)) or 0
    information_total = (
        db.scalar(select(func.count(InformationItem.id)).where(*information_filters)) or 0
    )
    event_total = (
        db.scalar(
            select(func.count(Event.id))
            .join(InformationItem, InformationItem.id == Event.information_id)
            .where(*event_filters)
        )
        or 0
    )
    reminder_total = (
        db.scalar(
            select(func.count(EventReminder.id))
            .join(Event, Event.id == EventReminder.event_id)
            .join(InformationItem, InformationItem.id == Event.information_id)
            .where(*reminder_filters)
        )
        or 0
    )
    return {
        "message_total": int(message_total),
        "information_active_total": int(information_total),
        "event_upcoming_total": int(event_total),
        "reminder_due_total": int(reminder_total),
    }


def channel_statistics(
    db: Session,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Call the required stored procedure and consume its first result set."""

    result = db.execute(
        text("CALL sp_channel_statistics(:user_id, :start_at, :end_at)"),
        {"user_id": user_id, "start_at": start, "end_at": end},
    )
    rows = [dict(row) for row in result.mappings().all()]
    result.close()
    return rows


def category_statistics(
    db: Session,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
    include_archived: bool,
) -> list[dict[str, Any]]:
    """Count distinct InformationItems by shared Category."""

    filters = [
        InformationItem.user_id == user_id,
        InformationItem.created_at >= start,
        InformationItem.created_at < end,
    ]
    if not include_archived:
        filters.append(InformationItem.status != InformationStatus.ARCHIVED.value)
    rows = db.execute(
        select(
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            func.count(func.distinct(InformationItem.id)).label("information_count"),
        )
        .join(InformationCategory, InformationCategory.category_id == Category.id)
        .join(InformationItem, InformationItem.id == InformationCategory.information_id)
        .where(*filters)
        .group_by(Category.id, Category.name)
        .order_by(text("information_count DESC"), Category.id.asc())
    ).mappings()
    return [dict(row) for row in rows]


def tag_statistics(
    db: Session,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
    include_archived: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """Return current-user Tag popularity for the requested time window."""

    filters = [
        Tag.user_id == user_id,
        InformationItem.user_id == user_id,
        InformationItem.created_at >= start,
        InformationItem.created_at < end,
    ]
    if not include_archived:
        filters.append(InformationItem.status != InformationStatus.ARCHIVED.value)
    usage_count = func.count(func.distinct(InformationItem.id)).label("usage_count")
    rows = db.execute(
        select(
            Tag.id.label("tag_id"),
            Tag.name.label("tag_name"),
            usage_count,
        )
        .join(
            InformationTag,
            (InformationTag.tag_id == Tag.id) & (InformationTag.user_id == Tag.user_id),
        )
        .join(InformationItem, InformationItem.id == InformationTag.information_id)
        .where(*filters)
        .group_by(Tag.id, Tag.name)
        .order_by(usage_count.desc(), Tag.id.asc())
        .limit(limit)
    ).mappings()
    return [dict(row) for row in rows]


def upcoming_event_times(
    db: Session,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
) -> list[tuple[datetime | None, datetime | None]]:
    """Read current-user upcoming Event times through the database view."""

    rows = db.execute(
        text(
            """
            SELECT start_at, deadline
            FROM v_upcoming_events
            WHERE user_id = :user_id
              AND COALESCE(start_at, deadline) < :end_at
              AND COALESCE(deadline, start_at) >= :start_at
            ORDER BY COALESCE(start_at, deadline), event_id
            """
        ),
        {"user_id": user_id, "start_at": start, "end_at": end},
    ).all()
    return [(row.start_at, row.deadline) for row in rows]


def _event_overlaps(start: datetime, end: datetime):
    effective_start = case((Event.start_at.is_not(None), Event.start_at), else_=Event.deadline)
    effective_end = case((Event.deadline.is_not(None), Event.deadline), else_=Event.start_at)
    return and_(effective_start < end, effective_end >= start)

