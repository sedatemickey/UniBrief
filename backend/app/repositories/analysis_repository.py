"""Persistence operations for AI attempts and structured information writes."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.enums import DictionaryStatus, InformationStatus, MessageStatus
from app.models import (
    AIAnalysis,
    Category,
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
from app.schemas.ai import CandidateInformation


def get_owned_message(db: Session, user_id: int, message_id: int) -> Message | None:
    """Return one current-user Message."""

    return db.scalar(select(Message).where(Message.id == message_id, Message.user_id == user_id))


def get_owned_message_with_sender(
    db: Session, user_id: int, message_id: int
) -> tuple[Message, Sender] | None:
    """Return a Message and same-user Sender snapshot for prompt construction."""

    row = db.execute(
        select(Message, Sender)
        .join(
            Sender,
            (Sender.id == Message.sender_id) & (Sender.user_id == Message.user_id),
        )
        .where(Message.id == message_id, Message.user_id == user_id)
    ).one_or_none()
    return (row[0], row[1]) if row is not None else None


def count_owned_messages(db: Session, user_id: int, message_ids: list[int]) -> int:
    """Count distinct requested IDs that belong to the authenticated user."""

    return int(
        db.scalar(
            select(func.count(Message.id)).where(
                Message.user_id == user_id,
                Message.id.in_(message_ids),
            )
        )
        or 0
    )


def claim_for_retry(db: Session, user_id: int, message_id: int, now: datetime) -> bool:
    """Atomically claim a PENDING/FAILED Message for manual processing."""

    result = db.execute(
        update(Message)
        .where(
            Message.user_id == user_id,
            Message.id == message_id,
            Message.process_status.in_([MessageStatus.PENDING.value, MessageStatus.FAILED.value]),
        )
        .values(
            process_status=MessageStatus.PROCESSING.value,
            processing_started_at=now,
        )
    )
    return result.rowcount == 1


def list_candidate_information(
    db: Session,
    *,
    user_id: int,
    message_content: str,
    limit: int = 20,
) -> list[CandidateInformation]:
    """Rank a bounded recent current-user candidate set with simple lexical overlap."""

    recent = list(
        db.scalars(
            select(InformationItem)
            .where(
                InformationItem.user_id == user_id,
                InformationItem.status.in_(
                    [InformationStatus.ACTIVE.value, InformationStatus.UPDATED.value]
                ),
            )
            .order_by(InformationItem.updated_at.desc(), InformationItem.id.desc())
            .limit(50)
        )
    )
    message_tokens = _tokens(message_content)
    ranked = sorted(
        recent,
        key=lambda item: (
            len(message_tokens & _tokens(f"{item.title} {item.summary}")),
            item.updated_at,
            item.id,
        ),
        reverse=True,
    )
    overlapping = [
        item
        for item in ranked
        if message_tokens & _tokens(f"{item.title} {item.summary}")
    ]
    selected = (overlapping or ranked[:10])[:limit]
    if not selected:
        return []

    ids = [item.id for item in selected]
    category_rows = db.execute(
        select(InformationCategory.information_id, Category.name)
        .join(Category, Category.id == InformationCategory.category_id)
        .where(InformationCategory.information_id.in_(ids))
    ).all()
    tag_rows = db.execute(
        select(InformationTag.information_id, Tag.name)
        .join(
            Tag,
            (Tag.id == InformationTag.tag_id) & (Tag.user_id == InformationTag.user_id),
        )
        .where(InformationTag.user_id == user_id, InformationTag.information_id.in_(ids))
    ).all()
    events = {
        item.information_id: item
        for item in db.scalars(select(Event).where(Event.information_id.in_(ids)))
    }
    categories: dict[int, list[str]] = {item_id: [] for item_id in ids}
    tags: dict[int, list[str]] = {item_id: [] for item_id in ids}
    for item_id, name in category_rows:
        categories[item_id].append(name)
    for item_id, name in tag_rows:
        tags[item_id].append(name)
    return [
        CandidateInformation(
            id=item.id,
            version=item.version,
            title=item.title,
            summary=item.summary,
            importance=item.importance,
            categories=categories[item.id],
            tags=tags[item.id],
            event_start_at=events[item.id].start_at if item.id in events else None,
            event_deadline=events[item.id].deadline if item.id in events else None,
        )
        for item in selected
    ]


def add_analysis(db: Session, analysis: AIAnalysis) -> None:
    """Stage one successful or failed provider attempt."""

    db.add(analysis)


def add_information(db: Session, information: InformationItem) -> None:
    """Stage a new current-user InformationItem."""

    db.add(information)


def get_owned_information(
    db: Session, user_id: int, information_id: int
) -> InformationItem | None:
    """Return one InformationItem inside the user boundary."""

    return db.scalar(
        select(InformationItem).where(
            InformationItem.id == information_id,
            InformationItem.user_id == user_id,
        )
    )


def optimistic_update_information(
    db: Session,
    *,
    user_id: int,
    information_id: int,
    expected_version: int,
    title: str,
    summary: str,
    source_type: str,
    importance: int,
    confidence: float,
) -> bool:
    """Update an InformationItem only when its candidate version is unchanged."""

    result = db.execute(
        update(InformationItem)
        .where(
            InformationItem.id == information_id,
            InformationItem.user_id == user_id,
            InformationItem.version == expected_version,
        )
        .values(
            title=title,
            summary=summary,
            source_type=source_type,
            importance=importance,
            confidence=Decimal(str(confidence)),
            status=InformationStatus.UPDATED.value,
            version=InformationItem.version + 1,
            updated_at=func.now(),
        )
    )
    return result.rowcount == 1


def upsert_message_relation(
    db: Session,
    *,
    user_id: int,
    message_id: int,
    information_id: int,
    relation_type: str,
) -> None:
    """Create the evidence edge or update its explicit semantic type."""

    relation = db.get(MessageInformation, (message_id, information_id))
    if relation is None:
        db.add(
            MessageInformation(
                user_id=user_id,
                message_id=message_id,
                information_id=information_id,
                relation_type=relation_type,
            )
        )
    else:
        relation.relation_type = relation_type


def get_or_create_category(db: Session, name: str) -> Category:
    """Resolve the global normalized Category dictionary by name."""

    category = db.scalar(select(Category).where(Category.name == name))
    if category is None:
        category = Category(
            name=name,
            description="AI 分析自动归一化分类",
            status=DictionaryStatus.ACTIVE.value,
        )
        db.add(category)
        db.flush()
    return category


def get_or_create_tag(db: Session, user_id: int, name: str) -> Tag:
    """Resolve or create a private user Tag."""

    tag = db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.name == name))
    if tag is None:
        tag = Tag(user_id=user_id, name=name)
        db.add(tag)
        db.flush()
    return tag


def set_information_categories(
    db: Session,
    *,
    information_id: int,
    names: list[str],
    replace: bool,
) -> None:
    """Replace or supplement Category edges using normalized names."""

    if replace:
        db.execute(
            delete(InformationCategory).where(
                InformationCategory.information_id == information_id
            )
        )
    existing = set(
        db.scalars(
            select(InformationCategory.category_id).where(
                InformationCategory.information_id == information_id
            )
        )
    )
    for name in names:
        category = get_or_create_category(db, name)
        if category.id not in existing:
            db.add(
                InformationCategory(
                    information_id=information_id,
                    category_id=category.id,
                )
            )
            existing.add(category.id)


def set_information_tags(
    db: Session,
    *,
    user_id: int,
    information_id: int,
    names: list[str],
    replace: bool,
) -> None:
    """Replace or supplement private Tag edges."""

    if replace:
        db.execute(
            delete(InformationTag).where(
                InformationTag.user_id == user_id,
                InformationTag.information_id == information_id,
            )
        )
    existing = set(
        db.scalars(
            select(InformationTag.tag_id).where(
                InformationTag.user_id == user_id,
                InformationTag.information_id == information_id,
            )
        )
    )
    for name in names:
        tag = get_or_create_tag(db, user_id, name)
        if tag.id not in existing:
            db.add(
                InformationTag(
                    user_id=user_id,
                    information_id=information_id,
                    tag_id=tag.id,
                )
            )
            existing.add(tag.id)


def get_event(db: Session, information_id: int) -> Event | None:
    """Return the one optional Event for an InformationItem."""

    return db.scalar(select(Event).where(Event.information_id == information_id))


def get_reminder(db: Session, event_id: int) -> EventReminder | None:
    """Return the one optional reminder for an Event."""

    return db.scalar(select(EventReminder).where(EventReminder.event_id == event_id))


def _tokens(value: str) -> set[str]:
    normalized = re.sub(r"\s+", "", value.casefold())
    words = set(re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", value.casefold()))
    grams = {normalized[index : index + 2] for index in range(max(0, len(normalized) - 1))}
    return words | grams
