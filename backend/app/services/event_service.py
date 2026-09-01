"""Business rules for Event editing and the in-app Reminder center."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil

from sqlalchemy.orm import Session

from app.core.enums import EventStatus, ReminderStatus
from app.core.errors import AppError
from app.models import EventReminder
from app.repositories import event_repository, information_repository
from app.schemas.information import (
    EventDetail,
    EventListItem,
    EventPage,
    EventPatch,
    ReminderListItem,
    ReminderPage,
    ReminderPatch,
    ReminderSummary,
)
from app.services.ingestion_service import utc_naive


def list_events(
    db: Session,
    *,
    user_id: int,
    range_start: datetime | None,
    range_end: datetime | None,
    status: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> EventPage:
    """List current-user Events for calendar and agenda views."""

    window = _optional_range(range_start, range_end, "range_start", "range_end")
    rows, total = event_repository.list_events(
        db,
        user_id=user_id,
        range_start=window[0],
        range_end=window[1],
        status=status,
        sort=sort,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return EventPage(
        items=[_event_item(event, information) for event, information in rows],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


def get_event(db: Session, *, user_id: int, event_id: int) -> EventDetail:
    """Return one Event with Information version and Reminder."""

    row = event_repository.get_owned_event(db, user_id, event_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    event, information = row
    reminder = information_repository.reminder_for_event(db, event.id)
    item = _event_item(event, information)
    return EventDetail(
        **item.model_dump(),
        summary=information.summary,
        reminder=(
            ReminderSummary.model_validate(reminder, from_attributes=True)
            if reminder
            else None
        ),
    )


def patch_event(
    db: Session,
    *,
    user_id: int,
    event_id: int,
    payload: EventPatch,
) -> EventDetail:
    """Optimistically edit Event time/status and maintain its default Reminder."""

    row = event_repository.get_owned_event(db, user_id, event_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    event, information = row
    start_at = (
        utc_naive(payload.start_at)
        if "start_at" in payload.model_fields_set and payload.start_at is not None
        else None
        if "start_at" in payload.model_fields_set
        else event.start_at
    )
    deadline = (
        utc_naive(payload.deadline)
        if "deadline" in payload.model_fields_set and payload.deadline is not None
        else None
        if "deadline" in payload.model_fields_set
        else event.deadline
    )
    if start_at is None and deadline is None:
        raise AppError(400, "VALIDATION_ERROR", "事项至少需要 start_at 或 deadline")
    if start_at is not None and deadline is not None and deadline < start_at:
        raise AppError(400, "VALIDATION_ERROR", "deadline 不能早于 start_at")
    if not information_repository.optimistic_patch_information(
        db,
        user_id=user_id,
        information_id=information.id,
        expected_version=payload.expected_information_version,
        values={},
    ):
        db.rollback()
        latest = information_repository.get_owned_information(db, user_id, information.id)
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "事项对应信息已被其他操作更新",
            retryable=True,
            details={"current_version": latest.version if latest else None},
        )
    event.start_at = start_at
    event.deadline = deadline
    if payload.event_status is not None:
        event.event_status = payload.event_status
    _maintain_reminder(db, event, deadline)
    db.commit()
    return get_event(db, user_id=user_id, event_id=event_id)


def list_reminders(
    db: Session,
    *,
    user_id: int,
    status: str | None,
    remind_from: datetime | None,
    remind_to: datetime | None,
    page: int,
    page_size: int,
) -> ReminderPage:
    """List current-user reminders for the notification center."""

    window = _optional_range(remind_from, remind_to, "remind_from", "remind_to")
    rows, total = event_repository.list_reminders(
        db,
        user_id=user_id,
        status=status,
        remind_from=window[0],
        remind_to=window[1],
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return ReminderPage(
        items=[
            ReminderListItem(
                id=reminder.id,
                event_id=event.id,
                information_id=information.id,
                title=information.title,
                deadline=event.deadline,
                remind_at=reminder.remind_at,
                reminder_status=reminder.reminder_status,
                is_custom_time=reminder.is_custom_time,
                triggered_at=reminder.triggered_at,
                read_at=reminder.read_at,
            )
            for reminder, event, information in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


def patch_reminder(
    db: Session,
    *,
    user_id: int,
    reminder_id: int,
    payload: ReminderPatch,
) -> ReminderListItem:
    """Customize, disable, or re-enable one owned Reminder."""

    row = event_repository.get_owned_reminder(db, user_id, reminder_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    reminder, event, information = row
    custom_time = utc_naive(payload.remind_at) if payload.remind_at is not None else None
    if custom_time is not None:
        reminder.remind_at = custom_time
        reminder.is_custom_time = True
    if payload.enabled is False:
        reminder.reminder_status = ReminderStatus.DISABLED.value
    elif payload.enabled is True:
        if reminder.remind_at is None:
            raise AppError(400, "VALIDATION_ERROR", "没有可用提醒时间")
        reminder.reminder_status = _time_status(reminder.remind_at)
        reminder.triggered_at = _now() if reminder.reminder_status == "DUE" else None
        reminder.read_at = None
    elif custom_time is not None and reminder.reminder_status != ReminderStatus.DISABLED.value:
        reminder.reminder_status = _time_status(custom_time)
        reminder.triggered_at = _now() if reminder.reminder_status == "DUE" else None
        reminder.read_at = None
    db.commit()
    return ReminderListItem(
        id=reminder.id,
        event_id=event.id,
        information_id=information.id,
        title=information.title,
        deadline=event.deadline,
        remind_at=reminder.remind_at,
        reminder_status=reminder.reminder_status,
        is_custom_time=reminder.is_custom_time,
        triggered_at=reminder.triggered_at,
        read_at=reminder.read_at,
    )


def read_reminder(db: Session, *, user_id: int, reminder_id: int) -> ReminderListItem:
    """Mark one DUE Reminder READ, with idempotent repeated reads."""

    row = event_repository.get_owned_reminder(db, user_id, reminder_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    reminder, event, information = row
    if reminder.reminder_status == ReminderStatus.DUE.value:
        reminder.reminder_status = ReminderStatus.READ.value
        reminder.read_at = _now()
        db.commit()
    elif reminder.reminder_status != ReminderStatus.READ.value:
        raise AppError(409, "INVALID_STATE", "仅到期提醒可标记已读")
    return ReminderListItem(
        id=reminder.id,
        event_id=event.id,
        information_id=information.id,
        title=information.title,
        deadline=event.deadline,
        remind_at=reminder.remind_at,
        reminder_status=reminder.reminder_status,
        is_custom_time=reminder.is_custom_time,
        triggered_at=reminder.triggered_at,
        read_at=reminder.read_at,
    )


def _maintain_reminder(db: Session, event: object, deadline: datetime | None) -> None:
    reminder = information_repository.reminder_for_event(db, event.id)
    terminal = event.event_status in {
        EventStatus.COMPLETED.value,
        EventStatus.CANCELLED.value,
        EventStatus.EXPIRED.value,
    }
    if terminal:
        if reminder and reminder.reminder_status == ReminderStatus.PENDING.value:
            reminder.reminder_status = ReminderStatus.DISABLED.value
        return
    if deadline is None:
        if reminder and not reminder.is_custom_time and reminder.reminder_status != "DISABLED":
            reminder.reminder_status = ReminderStatus.DISABLED.value
        return
    if reminder is None:
        remind_at = deadline - timedelta(hours=24)
        db.add(
            EventReminder(
                event_id=event.id,
                remind_at=remind_at,
                reminder_status=_time_status(remind_at),
                is_custom_time=False,
            )
        )
        return
    if reminder.is_custom_time or reminder.reminder_status == ReminderStatus.DISABLED.value:
        return
    reminder.remind_at = deadline - timedelta(hours=24)
    reminder.reminder_status = _time_status(reminder.remind_at)
    reminder.triggered_at = _now() if reminder.reminder_status == "DUE" else None
    reminder.read_at = None


def _event_item(event: object, information: object) -> EventListItem:
    return EventListItem(
        id=event.id,
        information_id=information.id,
        information_version=information.version,
        title=information.title,
        importance=information.importance,
        start_at=event.start_at,
        deadline=event.deadline,
        event_status=event.event_status,
        updated_at=event.updated_at,
    )


def _optional_range(
    start: datetime | None,
    end: datetime | None,
    start_name: str,
    end_name: str,
) -> tuple[datetime | None, datetime | None]:
    if (start is None) != (end is None):
        raise AppError(400, "VALIDATION_ERROR", f"{start_name} 和 {end_name} 必须同时提供")
    if start is None or end is None:
        return None, None
    start_utc, end_utc = utc_naive(start), utc_naive(end)
    if start_utc >= end_utc:
        raise AppError(400, "VALIDATION_ERROR", "时间范围起点必须早于终点")
    return start_utc, end_utc


def _time_status(remind_at: datetime) -> str:
    return ReminderStatus.DUE.value if remind_at <= _now() else ReminderStatus.PENDING.value


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

