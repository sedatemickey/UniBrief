"""Persistence queries for Message evidence, imports, and detail pages."""

from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models import AIAnalysis, Channel, Message, MessageAttachment, Platform, Sender


def get_by_external(
    db: Session, *, user_id: int, channel_id: int, external_id: str
) -> Message | None:
    """Execute the scoped persistence operation."""

    return db.scalar(
        select(Message).where(
            Message.user_id == user_id,
            Message.channel_id == channel_id,
            Message.external_id == external_id,
        )
    )


def add_message(db: Session, message: Message) -> None:
    """Execute the scoped persistence operation."""

    db.add(message)


def attachment_external_ids(db: Session, message_id: int) -> set[str]:
    """Execute the scoped persistence operation."""

    return set(
        db.scalars(
            select(MessageAttachment.external_id).where(MessageAttachment.message_id == message_id)
        )
    )


def add_attachment(db: Session, attachment: MessageAttachment) -> None:
    """Execute the scoped persistence operation."""

    db.add(attachment)


def list_page(
    db: Session,
    *,
    user_id: int,
    platform_id: int | None,
    channel_id: int | None,
    sender_id: int | None,
    process_status: str | None,
    sent_from: datetime | None,
    sent_to: datetime | None,
    keyword: str | None,
    has_attachment: bool | None,
    sort: str,
    offset: int,
    limit: int,
) -> tuple[list[Message], int]:
    """Execute the scoped persistence operation."""

    filters = [Message.user_id == user_id]
    if sent_from is not None and sent_to is not None:
        filters.extend([Message.sent_at >= sent_from, Message.sent_at < sent_to])
    if platform_id is not None:
        filters.append(Channel.platform_id == platform_id)
    if channel_id is not None:
        filters.append(Message.channel_id == channel_id)
    if sender_id is not None:
        filters.append(Message.sender_id == sender_id)
    if process_status:
        filters.append(Message.process_status == process_status)
    if keyword:
        filters.append(Message.content.like(f"%{keyword}%"))
    attachment_exists = exists(
        select(MessageAttachment.id).where(MessageAttachment.message_id == Message.id)
    )
    if has_attachment is True:
        filters.append(attachment_exists)
    elif has_attachment is False:
        filters.append(~attachment_exists)
    base = select(Message).join(Channel, Channel.id == Message.channel_id).where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    if sort == "sent_at_asc":
        order = (Message.sent_at.asc(), Message.id.asc())
    elif sort == "ingested_at_desc":
        order = (Message.ingested_at.desc(), Message.id.desc())
    else:
        order = (Message.sent_at.desc(), Message.id.desc())
    items = list(db.scalars(base.order_by(*order).offset(offset).limit(limit)))
    return items, total


def get_detail_row(
    db: Session, *, user_id: int, message_id: int
) -> tuple[Message, Channel, Sender, Platform] | None:
    """Execute the scoped persistence operation."""

    row = db.execute(
        select(Message, Channel, Sender, Platform)
        .join(Channel, Channel.id == Message.channel_id)
        .join(Sender, Sender.id == Message.sender_id)
        .join(Platform, Platform.id == Channel.platform_id)
        .where(Message.id == message_id, Message.user_id == user_id)
    ).one_or_none()
    return tuple(row) if row is not None else None


def list_attachments(db: Session, message_id: int) -> list[MessageAttachment]:
    """Execute the scoped persistence operation."""

    return list(
        db.scalars(
            select(MessageAttachment)
            .where(MessageAttachment.message_id == message_id)
            .order_by(MessageAttachment.id.asc())
        )
    )


def list_analyses(db: Session, message_id: int) -> list[AIAnalysis]:
    """Execute the scoped persistence operation."""

    return list(
        db.scalars(
            select(AIAnalysis)
            .where(AIAnalysis.message_id == message_id)
            .order_by(AIAnalysis.analyzed_at.desc(), AIAnalysis.id.desc())
        )
    )
