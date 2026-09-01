"""Persistence queries for authorized attachment lifecycle operations."""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Message, MessageAttachment


def get(db: Session, attachment_id: int) -> MessageAttachment | None:
    """Execute the scoped persistence operation."""

    return db.get(MessageAttachment, attachment_id)


def get_owned(db: Session, *, attachment_id: int, user_id: int) -> MessageAttachment | None:
    """Execute the scoped persistence operation."""

    return db.scalar(
        select(MessageAttachment)
        .join(Message, Message.id == MessageAttachment.message_id)
        .where(MessageAttachment.id == attachment_id, Message.user_id == user_id)
    )


def get_message(db: Session, message_id: int) -> Message | None:
    """Execute the scoped persistence operation."""

    return db.get(Message, message_id)


def recoverable(
    db: Session,
    *,
    pending_status: str,
    downloading_status: str,
    stale_before: datetime,
    max_attempts: int,
) -> list[MessageAttachment]:
    """Execute the scoped persistence operation."""

    return list(
        db.scalars(
            select(MessageAttachment).where(
                or_(
                    MessageAttachment.download_status == pending_status,
                    (MessageAttachment.download_status == downloading_status)
                    & (MessageAttachment.updated_at < stale_before),
                ),
                MessageAttachment.download_attempts < max_attempts,
            )
        )
    )


def by_status(db: Session, status: str) -> list[MessageAttachment]:
    """Execute the scoped persistence operation."""

    return list(
        db.scalars(select(MessageAttachment).where(MessageAttachment.download_status == status))
    )
