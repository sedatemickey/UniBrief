"""User-owned Channel and Sender source-management services."""

from decimal import Decimal
from math import ceil

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Channel, Platform, Sender
from app.repositories import dictionary_repository, source_repository
from app.schemas.resources import ChannelCreate, ChannelPatch, SenderCreate, SenderPatch


def active_platform_or_404(db: Session, platform_id: int) -> Platform:
    """Load an active administrator-provisioned platform."""

    platform = dictionary_repository.get_active_platform(db, platform_id)
    if platform is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    return platform


def list_channels(
    db: Session,
    *,
    user_id: int,
    platform_id: int | None,
    keyword: str | None,
    channel_type: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Channel], int, int]:
    """List channels strictly within one normal user's private space."""

    items, total = source_repository.list_channels(
        db,
        user_id=user_id,
        platform_id=platform_id,
        keyword=keyword,
        channel_type=channel_type,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return items, total, ceil(total / page_size) if total else 0


def create_channel(db: Session, user_id: int, payload: ChannelCreate) -> tuple[Channel, bool]:
    """Create a channel idempotently or reject conflicting external metadata."""

    active_platform_or_404(db, payload.platform_id)
    existing = source_repository.get_channel_by_external(
        db,
        user_id=user_id,
        platform_id=payload.platform_id,
        external_id=payload.external_id,
    )
    if existing is not None:
        if existing.name == payload.name and existing.channel_type == payload.channel_type:
            return existing, False
        raise AppError(409, "DUPLICATE_CONFLICT", "渠道外部 ID 已存在但内容不一致")
    channel = Channel(user_id=user_id, **payload.model_dump())
    source_repository.add_channel(db, channel)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "DUPLICATE_CONFLICT", "渠道外部 ID 已存在") from exc
    db.refresh(channel)
    return channel, True


def update_channel(db: Session, user_id: int, channel_id: int, payload: ChannelPatch) -> Channel:
    """Update only mutable fields of a user-owned channel."""

    channel = source_repository.get_owned_channel(db, user_id=user_id, channel_id=channel_id)
    if channel is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(channel, key, value)
    db.commit()
    db.refresh(channel)
    return channel


def list_senders(
    db: Session,
    *,
    user_id: int,
    platform_id: int | None,
    keyword: str | None,
    source_type: str | None,
    credibility_min: Decimal | None,
    credibility_max: Decimal | None,
    page: int,
    page_size: int,
) -> tuple[list[Sender], int, int]:
    """List senders strictly within one normal user's private space."""

    if credibility_min is not None and credibility_max is not None:
        if credibility_min > credibility_max:
            raise AppError(400, "VALIDATION_ERROR", "可信度下限不能大于上限")
    items, total = source_repository.list_senders(
        db,
        user_id=user_id,
        platform_id=platform_id,
        keyword=keyword,
        source_type=source_type,
        credibility_min=credibility_min,
        credibility_max=credibility_max,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return items, total, ceil(total / page_size) if total else 0


def create_sender(db: Session, user_id: int, payload: SenderCreate) -> tuple[Sender, bool]:
    """Create a sender idempotently or reject conflicting external metadata."""

    active_platform_or_404(db, payload.platform_id)
    existing = source_repository.get_sender_by_external(
        db,
        user_id=user_id,
        platform_id=payload.platform_id,
        external_id=payload.external_id,
    )
    if existing is not None:
        exact = (
            existing.display_name == payload.display_name
            and existing.source_type == payload.source_type
            and existing.credibility == payload.credibility
        )
        if exact:
            return existing, False
        raise AppError(409, "DUPLICATE_CONFLICT", "发送者外部 ID 已存在但内容不一致")
    sender = Sender(user_id=user_id, **payload.model_dump())
    source_repository.add_sender(db, sender)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "DUPLICATE_CONFLICT", "发送者外部 ID 已存在") from exc
    db.refresh(sender)
    return sender, True


def update_sender(db: Session, user_id: int, sender_id: int, payload: SenderPatch) -> Sender:
    """Update only mutable fields of a user-owned sender."""

    sender = source_repository.get_owned_sender(db, user_id=user_id, sender_id=sender_id)
    if sender is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(sender, key, value)
    db.commit()
    db.refresh(sender)
    return sender
