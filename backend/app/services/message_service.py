"""User-scoped Message queries and evidence detail loading."""

from datetime import datetime
from math import ceil

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import AIAnalysis, Channel, Message, MessageAttachment, Platform, Sender
from app.repositories import message_repository
from app.services.ingestion_service import utc_naive


def list_messages(
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
    page: int,
    page_size: int,
) -> tuple[list[Message], int, int]:
    """List messages with stable pagination and mandatory ownership filtering."""

    if (sent_from is None) != (sent_to is None):
        raise AppError(400, "VALIDATION_ERROR", "sent_from 和 sent_to 必须同时提供")
    start = end = None
    if sent_from is not None and sent_to is not None:
        start = utc_naive(sent_from)
        end = utc_naive(sent_to)
        if start >= end:
            raise AppError(400, "VALIDATION_ERROR", "时间范围起点必须早于终点")
    items, total = message_repository.list_page(
        db,
        user_id=user_id,
        platform_id=platform_id,
        channel_id=channel_id,
        sender_id=sender_id,
        process_status=process_status,
        sent_from=start,
        sent_to=end,
        keyword=keyword,
        has_attachment=has_attachment,
        sort=sort,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return items, total, ceil(total / page_size) if total else 0


def get_message_detail(
    db: Session, *, user_id: int, message_id: int
) -> tuple[Message, Channel, Sender, Platform, list[MessageAttachment], list[AIAnalysis]]:
    """Load Message evidence and child records without crossing user boundaries."""

    row = message_repository.get_detail_row(db, user_id=user_id, message_id=message_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    message, channel, sender, platform = row
    return (
        message,
        channel,
        sender,
        platform,
        message_repository.list_attachments(db, message.id),
        message_repository.list_analyses(db, message.id),
    )
