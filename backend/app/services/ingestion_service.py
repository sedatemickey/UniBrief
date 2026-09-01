"""Idempotent JSON message ingestion with user-scoped evidence preservation."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Channel, Message, MessageAttachment, Platform, Sender
from app.repositories import (
    dictionary_repository,
    message_repository,
    source_repository,
)
from app.schemas.messages import (
    ImportAttachment,
    ImportItemError,
    ImportItemResult,
    MessageImportItem,
    MessageImportRequest,
    MessageImportResponse,
)


def utc_naive(value: datetime) -> datetime:
    """Convert a required aware timestamp to a naive UTC DATETIME value."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise AppError(400, "VALIDATION_ERROR", "时间必须包含时区")
    return value.astimezone(UTC).replace(tzinfo=None)


def _attachment_external_id(attachment: ImportAttachment) -> str:
    if attachment.external_id:
        return attachment.external_id
    material = f"{attachment.file_url}\n{attachment.file_name}".encode()
    return sha256(material).hexdigest()


def _get_platform(db: Session, request: MessageImportRequest) -> Platform | None:
    return dictionary_repository.get_active_platform_by_identity(
        db, name=request.platform.name, platform_type=request.platform.type
    )


def _get_or_create_channel(
    db: Session, *, user_id: int, platform: Platform, request: MessageImportRequest
) -> Channel:
    channel = source_repository.get_channel_by_external(
        db,
        user_id=user_id,
        platform_id=platform.id,
        external_id=request.channel.external_id,
    )
    if channel is not None:
        return channel
    channel = Channel(
        user_id=user_id,
        platform_id=platform.id,
        external_id=request.channel.external_id,
        name=request.channel.name,
        channel_type=request.channel.channel_type,
    )
    source_repository.add_channel(db, channel)
    db.commit()
    db.refresh(channel)
    return channel


def _get_or_create_sender(
    db: Session, *, user_id: int, platform_id: int, item: MessageImportItem
) -> Sender:
    sender = source_repository.get_sender_by_external(
        db,
        user_id=user_id,
        platform_id=platform_id,
        external_id=item.sender.external_id,
    )
    if sender is not None:
        return sender
    sender = Sender(
        user_id=user_id,
        platform_id=platform_id,
        external_id=item.sender.external_id,
        display_name=item.sender.display_name,
        source_type=item.sender.source_type,
    )
    source_repository.add_sender(db, sender)
    db.flush()
    return sender


def _add_missing_attachments(
    db: Session, message: Message, attachments: list[ImportAttachment]
) -> list[int]:
    existing_ids = message_repository.attachment_external_ids(db, message.id)
    created: list[MessageAttachment] = []
    for attachment in attachments:
        external_id = _attachment_external_id(attachment)
        if external_id in existing_ids:
            continue
        row = MessageAttachment(
            message_id=message.id,
            external_id=external_id,
            file_name=attachment.file_name,
            file_type=attachment.file_type,
            file_url=attachment.file_url,
        )
        message_repository.add_attachment(db, row)
        created.append(row)
        existing_ids.add(external_id)
    db.flush()
    return [row.id for row in created]


def _invalid_item_result(raw: dict, error: ValidationError) -> ImportItemResult:
    external_id = raw.get("external_id")
    if not isinstance(external_id, str) or not external_id:
        external_id = "<invalid>"
    first = error.errors()[0]
    return ImportItemResult(
        external_id=external_id,
        status="FAILED",
        error=ImportItemError(
            code="VALIDATION_ERROR",
            message=f"{'.'.join(map(str, first['loc']))}: {first['msg']}",
        ),
    )


def import_messages(
    db: Session, *, user_id: int, request: MessageImportRequest
) -> tuple[MessageImportResponse, list[int]]:
    """Import each message independently and return attachment IDs to schedule."""

    platform = _get_platform(db, request)
    if platform is None:
        results = []
        for raw in request.messages:
            external_id = raw.get("external_id") if isinstance(raw, dict) else None
            results.append(
                ImportItemResult(
                    external_id=(
                        external_id if isinstance(external_id, str) and external_id else "<invalid>"
                    ),
                    status="FAILED",
                    error=ImportItemError(
                        code="PLATFORM_NOT_AVAILABLE",
                        message="平台不存在、已停用或类型不匹配",
                    ),
                )
            )
        response = MessageImportResponse(
            received=len(results),
            inserted=0,
            duplicates=0,
            failed=len(results),
            attachment_metadata_created=0,
            attachment_downloads_scheduled=0,
            results=results,
        )
        raise AppError(
            400,
            "IMPORT_PARTIAL_FAILURE",
            "所有消息导入失败",
            details=response.model_dump(mode="json"),
        )

    parsed_items: list[MessageImportItem | ImportItemResult] = []
    for raw in request.messages:
        try:
            parsed_items.append(MessageImportItem.model_validate(raw))
        except ValidationError as exc:
            parsed_items.append(_invalid_item_result(raw, exc))
    if not any(isinstance(item, MessageImportItem) for item in parsed_items):
        invalid_results = [item for item in parsed_items if isinstance(item, ImportItemResult)]
        response = MessageImportResponse(
            received=len(request.messages),
            inserted=0,
            duplicates=0,
            failed=len(request.messages),
            attachment_metadata_created=0,
            attachment_downloads_scheduled=0,
            results=invalid_results,
        )
        raise AppError(
            400,
            "IMPORT_PARTIAL_FAILURE",
            "所有消息导入失败",
            details=response.model_dump(mode="json"),
        )

    channel = _get_or_create_channel(db, user_id=user_id, platform=platform, request=request)
    results: list[ImportItemResult] = []
    download_ids: list[int] = []
    inserted = duplicates = failed = attachment_count = 0

    for parsed in parsed_items:
        if isinstance(parsed, ImportItemResult):
            failed += 1
            results.append(parsed)
            continue
        item = parsed
        sent_at = utc_naive(item.sent_at)
        try:
            sender = _get_or_create_sender(db, user_id=user_id, platform_id=platform.id, item=item)
            existing = message_repository.get_by_external(
                db,
                user_id=user_id,
                channel_id=channel.id,
                external_id=item.external_id,
            )
            if existing is not None:
                if (
                    existing.sender_id != sender.id
                    or existing.content != item.content
                    or existing.sent_at != sent_at
                ):
                    existing_id = existing.id
                    db.rollback()
                    failed += 1
                    results.append(
                        ImportItemResult(
                            external_id=item.external_id,
                            status="FAILED",
                            message_id=existing_id,
                            error=ImportItemError(
                                code="DUPLICATE_CONFLICT",
                                message="相同外部 ID 的核心消息内容不一致",
                            ),
                        )
                    )
                    continue
                created_ids = _add_missing_attachments(db, existing, item.attachments)
                db.commit()
                duplicates += 1
                attachment_count += len(created_ids)
                download_ids.extend(created_ids)
                results.append(
                    ImportItemResult(
                        external_id=item.external_id,
                        status="DUPLICATE",
                        message_id=existing.id,
                    )
                )
                continue

            message = Message(
                user_id=user_id,
                channel_id=channel.id,
                sender_id=sender.id,
                external_id=item.external_id,
                content=item.content,
                sent_at=sent_at,
            )
            message_repository.add_message(db, message)
            db.flush()
            created_ids = _add_missing_attachments(db, message, item.attachments)
            db.commit()
            inserted += 1
            attachment_count += len(created_ids)
            download_ids.extend(created_ids)
            results.append(
                ImportItemResult(
                    external_id=item.external_id,
                    status="INSERTED",
                    message_id=message.id,
                )
            )
        except IntegrityError:
            db.rollback()
            failed += 1
            results.append(
                ImportItemResult(
                    external_id=item.external_id,
                    status="FAILED",
                    error=ImportItemError(
                        code="DUPLICATE_CONFLICT",
                        message="消息导入发生唯一约束冲突",
                    ),
                )
            )

    response = MessageImportResponse(
        received=len(request.messages),
        inserted=inserted,
        duplicates=duplicates,
        failed=failed,
        attachment_metadata_created=attachment_count,
        attachment_downloads_scheduled=len(download_ids),
        results=results,
    )
    if failed == len(request.messages):
        raise AppError(
            400,
            "IMPORT_PARTIAL_FAILURE",
            "所有消息导入失败",
            details=response.model_dump(mode="json"),
        )
    return response, download_ids
