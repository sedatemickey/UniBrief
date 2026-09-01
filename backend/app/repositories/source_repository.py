"""Persistence queries for user-owned Channel and Sender sources."""

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Channel, Sender


def list_channels(
    db: Session,
    *,
    user_id: int,
    platform_id: int | None,
    keyword: str | None,
    channel_type: str | None,
    offset: int,
    limit: int,
) -> tuple[list[Channel], int]:
    """Execute the scoped persistence operation."""

    filters = [Channel.user_id == user_id]
    if platform_id is not None:
        filters.append(Channel.platform_id == platform_id)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(or_(Channel.name.like(pattern), Channel.external_id.like(pattern)))
    if channel_type:
        filters.append(Channel.channel_type == channel_type)
    total = db.scalar(select(func.count()).select_from(Channel).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Channel)
            .where(*filters)
            .order_by(Channel.created_at.desc(), Channel.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def get_channel_by_external(
    db: Session, *, user_id: int, platform_id: int, external_id: str
) -> Channel | None:
    """Execute the scoped persistence operation."""

    return db.scalar(
        select(Channel).where(
            Channel.user_id == user_id,
            Channel.platform_id == platform_id,
            Channel.external_id == external_id,
        )
    )


def get_owned_channel(db: Session, *, user_id: int, channel_id: int) -> Channel | None:
    """Execute the scoped persistence operation."""

    return db.scalar(select(Channel).where(Channel.id == channel_id, Channel.user_id == user_id))


def add_channel(db: Session, channel: Channel) -> None:
    """Execute the scoped persistence operation."""

    db.add(channel)


def list_senders(
    db: Session,
    *,
    user_id: int,
    platform_id: int | None,
    keyword: str | None,
    source_type: str | None,
    credibility_min: Decimal | None,
    credibility_max: Decimal | None,
    offset: int,
    limit: int,
) -> tuple[list[Sender], int]:
    """Execute the scoped persistence operation."""

    filters = [Sender.user_id == user_id]
    if platform_id is not None:
        filters.append(Sender.platform_id == platform_id)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(or_(Sender.display_name.like(pattern), Sender.external_id.like(pattern)))
    if source_type:
        filters.append(Sender.source_type == source_type)
    if credibility_min is not None:
        filters.append(Sender.credibility >= credibility_min)
    if credibility_max is not None:
        filters.append(Sender.credibility <= credibility_max)
    total = db.scalar(select(func.count()).select_from(Sender).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Sender)
            .where(*filters)
            .order_by(Sender.created_at.desc(), Sender.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def get_sender_by_external(
    db: Session, *, user_id: int, platform_id: int, external_id: str
) -> Sender | None:
    """Execute the scoped persistence operation."""

    return db.scalar(
        select(Sender).where(
            Sender.user_id == user_id,
            Sender.platform_id == platform_id,
            Sender.external_id == external_id,
        )
    )


def get_owned_sender(db: Session, *, user_id: int, sender_id: int) -> Sender | None:
    """Execute the scoped persistence operation."""

    return db.scalar(select(Sender).where(Sender.id == sender_id, Sender.user_id == user_id))


def add_sender(db: Session, sender: Sender) -> None:
    """Execute the scoped persistence operation."""

    db.add(sender)
