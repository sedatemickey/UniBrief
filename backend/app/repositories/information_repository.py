"""Persistence queries for Information, Tag, provenance, Event, and Reminder APIs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, exists, func, or_, select, update
from sqlalchemy.orm import Session

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
    Sender,
    Tag,
)


def list_information_ids(
    db: Session,
    *,
    user_id: int,
    category_ids: list[int],
    tag_ids: list[int],
    importance_min: int | None,
    importance_max: int | None,
    status: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    event_from: datetime | None,
    event_to: datetime | None,
    keyword: str | None,
    sort: str,
    offset: int,
    limit: int,
) -> tuple[list[int], int]:
    """Return one filtered page of current-user Information IDs."""

    filters = [InformationItem.user_id == user_id]
    if category_ids:
        filters.append(
            exists(
                select(InformationCategory.information_id).where(
                    InformationCategory.information_id == InformationItem.id,
                    InformationCategory.category_id.in_(category_ids),
                )
            )
        )
    if tag_ids:
        filters.append(
            exists(
                select(InformationTag.information_id).where(
                    InformationTag.user_id == user_id,
                    InformationTag.information_id == InformationItem.id,
                    InformationTag.tag_id.in_(tag_ids),
                )
            )
        )
    if importance_min is not None:
        filters.append(InformationItem.importance >= importance_min)
    if importance_max is not None:
        filters.append(InformationItem.importance <= importance_max)
    if status:
        filters.append(InformationItem.status == status)
    if created_from is not None and created_to is not None:
        filters.extend(
            [InformationItem.created_at >= created_from, InformationItem.created_at < created_to]
        )
    if keyword:
        filters.append(
            or_(
                InformationItem.title.like(f"%{keyword}%"),
                InformationItem.summary.like(f"%{keyword}%"),
            )
        )
    if event_from is not None and event_to is not None:
        effective_start = case((Event.start_at.is_not(None), Event.start_at), else_=Event.deadline)
        effective_end = case((Event.deadline.is_not(None), Event.deadline), else_=Event.start_at)
        filters.append(
            exists(
                select(Event.id).where(
                    Event.information_id == InformationItem.id,
                    effective_start < event_to,
                    effective_end >= event_from,
                )
            )
        )
    base = select(InformationItem.id).where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    deadline = (
        select(Event.deadline)
        .where(Event.information_id == InformationItem.id)
        .scalar_subquery()
    )
    if sort == "updated_at_desc":
        order = (InformationItem.updated_at.desc(), InformationItem.id.desc())
    elif sort == "importance_desc":
        order = (InformationItem.importance.desc(), InformationItem.created_at.desc())
    elif sort == "deadline_asc":
        order = (deadline.is_(None), deadline.asc(), InformationItem.id.asc())
    else:
        order = (InformationItem.created_at.desc(), InformationItem.id.desc())
    ids = list(db.scalars(base.order_by(*order).offset(offset).limit(limit)))
    return ids, int(total)


def get_owned_information(
    db: Session, user_id: int, information_id: int
) -> InformationItem | None:
    """Return one owned InformationItem."""

    return db.scalar(
        select(InformationItem).where(
            InformationItem.id == information_id,
            InformationItem.user_id == user_id,
        )
    )


def list_information(db: Session, user_id: int, ids: list[int]) -> list[InformationItem]:
    """Load an ordered set of owned InformationItems."""

    if not ids:
        return []
    rows = {
        item.id: item
        for item in db.scalars(
            select(InformationItem).where(
                InformationItem.user_id == user_id,
                InformationItem.id.in_(ids),
            )
        )
    }
    return [rows[item_id] for item_id in ids if item_id in rows]


def categories_for_information(
    db: Session, information_ids: list[int]
) -> dict[int, list[Category]]:
    """Load Category objects for Information IDs."""

    result = {item_id: [] for item_id in information_ids}
    if not information_ids:
        return result
    rows = db.execute(
        select(InformationCategory.information_id, Category)
        .join(Category, Category.id == InformationCategory.category_id)
        .where(InformationCategory.information_id.in_(information_ids))
        .order_by(Category.name)
    ).all()
    for information_id, category in rows:
        result[information_id].append(category)
    return result


def tags_for_information(
    db: Session, user_id: int, information_ids: list[int]
) -> dict[int, list[Tag]]:
    """Load same-user Tag objects for Information IDs."""

    result = {item_id: [] for item_id in information_ids}
    if not information_ids:
        return result
    rows = db.execute(
        select(InformationTag.information_id, Tag)
        .join(
            Tag,
            (Tag.id == InformationTag.tag_id) & (Tag.user_id == InformationTag.user_id),
        )
        .where(
            InformationTag.user_id == user_id,
            InformationTag.information_id.in_(information_ids),
        )
        .order_by(Tag.name)
    ).all()
    for information_id, tag in rows:
        result[information_id].append(tag)
    return result


def events_for_information(db: Session, information_ids: list[int]) -> dict[int, Event]:
    """Load optional Event objects keyed by Information ID."""

    if not information_ids:
        return {}
    return {
        event.information_id: event
        for event in db.scalars(select(Event).where(Event.information_id.in_(information_ids)))
    }


def reminder_for_event(db: Session, event_id: int) -> EventReminder | None:
    """Load the optional one-to-one EventReminder."""

    return db.scalar(select(EventReminder).where(EventReminder.event_id == event_id))


def information_sources(
    db: Session, *, user_id: int, information_id: int
) -> list[tuple[MessageInformation, Message, Channel, Sender]]:
    """Load provenance Messages without leaving the user boundary."""

    return list(
        db.execute(
            select(MessageInformation, Message, Channel, Sender)
            .join(
                Message,
                (Message.id == MessageInformation.message_id)
                & (Message.user_id == MessageInformation.user_id),
            )
            .join(Channel, Channel.id == Message.channel_id)
            .join(Sender, Sender.id == Message.sender_id)
            .where(
                MessageInformation.user_id == user_id,
                MessageInformation.information_id == information_id,
            )
            .order_by(Message.sent_at.desc(), Message.id.desc())
        ).all()
    )


def optimistic_patch_information(
    db: Session,
    *,
    user_id: int,
    information_id: int,
    expected_version: int,
    values: dict[str, object],
) -> bool:
    """Apply scalar changes only at the expected optimistic version."""

    values = {**values, "version": InformationItem.version + 1}
    result = db.execute(
        update(InformationItem)
        .where(
            InformationItem.id == information_id,
            InformationItem.user_id == user_id,
            InformationItem.version == expected_version,
        )
        .values(**values)
    )
    return result.rowcount == 1


def get_message_relation(
    db: Session, message_id: int, information_id: int
) -> MessageInformation | None:
    """Return one MessageInformation edge by composite key."""

    return db.get(MessageInformation, (message_id, information_id))


def get_owned_message(db: Session, user_id: int, message_id: int) -> Message | None:
    """Return one owned Message for manual provenance linking."""

    return db.scalar(
        select(Message).where(Message.id == message_id, Message.user_id == user_id)
    )


def list_tags(
    db: Session,
    *,
    user_id: int,
    keyword: str | None,
    offset: int,
    limit: int,
) -> tuple[list[Tag], int]:
    """List private Tags with paging."""

    filters = [Tag.user_id == user_id]
    if keyword:
        filters.append(Tag.name.like(f"%{keyword}%"))
    total = db.scalar(select(func.count(Tag.id)).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Tag)
            .where(*filters)
            .order_by(Tag.name, Tag.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return items, int(total)


def get_tag(db: Session, user_id: int, tag_id: int) -> Tag | None:
    """Return one private Tag."""

    return db.scalar(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id))


def get_tag_by_name(db: Session, user_id: int, name: str) -> Tag | None:
    """Resolve a private Tag by its unique name."""

    return db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.name == name))


def popular_tags(
    db: Session,
    *,
    user_id: int,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
) -> list[tuple[int, str, int]]:
    """Count distinct current-user InformationItems for each Tag."""

    filters = [Tag.user_id == user_id, InformationItem.user_id == user_id]
    if created_from is not None and created_to is not None:
        filters.extend(
            [InformationItem.created_at >= created_from, InformationItem.created_at < created_to]
        )
    count = func.count(func.distinct(InformationItem.id)).label("usage_count")
    rows = db.execute(
        select(Tag.id, Tag.name, count)
        .outerjoin(
            InformationTag,
            (InformationTag.tag_id == Tag.id) & (InformationTag.user_id == Tag.user_id),
        )
        .outerjoin(InformationItem, InformationItem.id == InformationTag.information_id)
        .where(*filters)
        .group_by(Tag.id, Tag.name)
        .order_by(count.desc(), Tag.name)
        .limit(limit)
    ).all()
    return [(row.id, row.name, row.usage_count) for row in rows]

