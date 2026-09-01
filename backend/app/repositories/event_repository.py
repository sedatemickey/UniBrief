"""Persistence queries for Event and Reminder list/detail APIs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Event, EventReminder, InformationItem


def list_events(
    db: Session,
    *,
    user_id: int,
    range_start: datetime | None,
    range_end: datetime | None,
    status: str | None,
    sort: str,
    offset: int,
    limit: int,
) -> tuple[list[tuple[Event, InformationItem]], int]:
    """List owned Event rows with optional overlap filtering."""

    filters = [InformationItem.user_id == user_id]
    if status:
        filters.append(Event.event_status == status)
    if range_start is not None and range_end is not None:
        effective_start = case((Event.start_at.is_not(None), Event.start_at), else_=Event.deadline)
        effective_end = case((Event.deadline.is_not(None), Event.deadline), else_=Event.start_at)
        filters.extend([effective_start < range_end, effective_end >= range_start])
    base = (
        select(Event, InformationItem)
        .join(InformationItem, InformationItem.id == Event.information_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    if sort == "deadline_asc":
        order = (Event.deadline.is_(None), Event.deadline.asc(), Event.id.asc())
    elif sort == "updated_at_desc":
        order = (Event.updated_at.desc(), Event.id.desc())
    else:
        order = (Event.start_at.is_(None), Event.start_at.asc(), Event.id.asc())
    rows = list(db.execute(base.order_by(*order).offset(offset).limit(limit)).all())
    return [(row[0], row[1]) for row in rows], int(total)


def get_owned_event(
    db: Session, user_id: int, event_id: int
) -> tuple[Event, InformationItem] | None:
    """Return one Event and its owned InformationItem."""

    row = db.execute(
        select(Event, InformationItem)
        .join(InformationItem, InformationItem.id == Event.information_id)
        .where(Event.id == event_id, InformationItem.user_id == user_id)
    ).one_or_none()
    return (row[0], row[1]) if row else None


def get_owned_reminder(
    db: Session, user_id: int, reminder_id: int
) -> tuple[EventReminder, Event, InformationItem] | None:
    """Return one Reminder through Event and Information ownership."""

    row = db.execute(
        select(EventReminder, Event, InformationItem)
        .join(Event, Event.id == EventReminder.event_id)
        .join(InformationItem, InformationItem.id == Event.information_id)
        .where(EventReminder.id == reminder_id, InformationItem.user_id == user_id)
    ).one_or_none()
    return (row[0], row[1], row[2]) if row else None


def list_reminders(
    db: Session,
    *,
    user_id: int,
    status: str | None,
    remind_from: datetime | None,
    remind_to: datetime | None,
    offset: int,
    limit: int,
) -> tuple[list[tuple[EventReminder, Event, InformationItem]], int]:
    """List owned reminders with status/time filtering."""

    filters = [InformationItem.user_id == user_id]
    if status:
        filters.append(EventReminder.reminder_status == status)
    if remind_from is not None and remind_to is not None:
        filters.extend(
            [EventReminder.remind_at >= remind_from, EventReminder.remind_at < remind_to]
        )
    base = (
        select(EventReminder, Event, InformationItem)
        .join(Event, Event.id == EventReminder.event_id)
        .join(InformationItem, InformationItem.id == Event.information_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.execute(
            base.order_by(EventReminder.remind_at.desc(), EventReminder.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return [(row[0], row[1], row[2]) for row in rows], int(total)
