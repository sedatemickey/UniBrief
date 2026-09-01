"""Message ingestion/query and authorized attachment routes."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.adapters.csv_adapter import CSV_MAX_BYTES, parse_csv
from app.api.dependencies import DbSession, current_user, user_csrf
from app.core.errors import AppError
from app.models import MessageAttachment, User
from app.schemas.ai import (
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    AnalyzeRequest,
    AnalyzeResponse,
)
from app.schemas.messages import (
    AttachmentResponse,
    AttachmentRetryResponse,
    MessageDetail,
    MessageImportRequest,
    MessageImportResponse,
    MessagePage,
    MessageResponse,
)
from app.services import analysis_service, attachment_service, ingestion_service, message_service

router = APIRouter(tags=["messages"])


def _schedule_attachments(background_tasks: BackgroundTasks, attachment_ids: list[int]) -> None:
    for attachment_id in attachment_ids:
        background_tasks.add_task(attachment_service.download_attachment, attachment_id)


@router.post("/messages/import", response_model=MessageImportResponse)
def import_json(
    payload: MessageImportRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> MessageImportResponse:
    """Import a user-scoped JSON batch and schedule committed attachment rows."""

    response, attachment_ids = ingestion_service.import_messages(
        db, user_id=user.id, request=payload
    )
    _schedule_attachments(background_tasks, attachment_ids)
    return response


@router.post("/messages/import-csv", response_model=MessageImportResponse)
async def import_csv(
    background_tasks: BackgroundTasks,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
    file: Annotated[UploadFile, File()],
) -> MessageImportResponse:
    """Convert a bounded UTF-8 CSV upload into one or more unified import batches."""

    content = await file.read(CSV_MAX_BYTES + 1)
    requests = parse_csv(content)
    responses: list[MessageImportResponse] = []
    attachment_ids: list[int] = []
    for request in requests:
        try:
            response, group_attachment_ids = ingestion_service.import_messages(
                db, user_id=user.id, request=request
            )
        except AppError as exc:
            if exc.code != "IMPORT_PARTIAL_FAILURE" or not isinstance(exc.details, dict):
                raise
            responses.append(MessageImportResponse.model_validate(exc.details))
        else:
            responses.append(response)
            attachment_ids.extend(group_attachment_ids)
    combined = MessageImportResponse(
        received=sum(item.received for item in responses),
        inserted=sum(item.inserted for item in responses),
        duplicates=sum(item.duplicates for item in responses),
        failed=sum(item.failed for item in responses),
        attachment_metadata_created=sum(item.attachment_metadata_created for item in responses),
        attachment_downloads_scheduled=len(attachment_ids),
        results=[result for item in responses for result in item.results],
    )
    if combined.failed == combined.received:
        raise AppError(
            400,
            "IMPORT_PARTIAL_FAILURE",
            "所有消息导入失败",
            details=combined.model_dump(mode="json"),
        )
    _schedule_attachments(background_tasks, attachment_ids)
    return combined


@router.get("/messages", response_model=MessagePage)
def messages(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    platform_id: int | None = None,
    channel_id: int | None = None,
    sender_id: int | None = None,
    process_status: str | None = None,
    sent_from: datetime | None = None,
    sent_to: datetime | None = None,
    keyword: str | None = None,
    has_attachment: bool | None = None,
    sort: Literal["sent_at_desc", "sent_at_asc", "ingested_at_desc"] = "sent_at_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MessagePage:
    """List current-user messages with server-side filters and pagination."""

    items, total, total_pages = message_service.list_messages(
        db,
        user_id=user.id,
        platform_id=platform_id,
        channel_id=channel_id,
        sender_id=sender_id,
        process_status=process_status,
        sent_from=sent_from,
        sent_to=sent_to,
        keyword=keyword,
        has_attachment=has_attachment,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return MessagePage(
        items=[MessageResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post("/messages/analyze-batch", response_model=AnalyzeBatchResponse)
async def analyze_message_batch(
    payload: AnalyzeBatchRequest,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> AnalyzeBatchResponse:
    """Analyze 1..100 owned Messages using independent short transactions."""

    return await analysis_service.analyze_batch(
        db,
        user_id=user.id,
        message_ids=payload.message_ids,
        requested_model=payload.model,
        mode=payload.mode,
    )


@router.post("/messages/{message_id}/analyze", response_model=AnalyzeResponse)
async def analyze_message(
    message_id: int,
    payload: AnalyzeRequest,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> AnalyzeResponse:
    """Run retry or compare analysis for one owned Message."""

    return await analysis_service.analyze_single(
        db,
        user_id=user.id,
        message_id=message_id,
        requested_model=payload.model,
        mode=payload.mode,
    )

@router.get("/messages/{message_id}", response_model=MessageDetail)
def message_detail(
    message_id: int,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
) -> MessageDetail:
    """Return one Message with source, attachment, and AI-attempt history."""

    message, channel, sender, platform, attachments, analyses = message_service.get_message_detail(
        db, user_id=user.id, message_id=message_id
    )
    return MessageDetail(
        **MessageResponse.model_validate(message).model_dump(),
        platform_id=platform.id,
        channel_name=channel.name,
        sender_display_name=sender.display_name,
        attachments=[AttachmentResponse.model_validate(item) for item in attachments],
        analyses=analyses,
    )


@router.get("/attachments/{attachment_id}", response_model=AttachmentResponse)
def attachment_metadata(
    attachment_id: int,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
) -> MessageAttachment:
    """Return safe attachment metadata without URL or storage paths."""

    return attachment_service.get_owned_attachment(db, attachment_id, user.id)


@router.post(
    "/attachments/{attachment_id}/retry-download",
    response_model=AttachmentRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_attachment(
    attachment_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> AttachmentRetryResponse:
    """Move an eligible attachment to PENDING and schedule another attempt."""

    attachment = attachment_service.schedule_retry(db, attachment_id, user.id)
    background_tasks.add_task(attachment_service.download_attachment, attachment.id)
    return AttachmentRetryResponse(
        id=attachment.id,
        download_status=attachment.download_status,
        scheduled=True,
    )


@router.get("/attachments/{attachment_id}/download", response_model=None)
def download_attachment_file(
    attachment_id: int,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
) -> FileResponse:
    """Stream an authorized local file without exposing its storage key."""

    attachment, path = attachment_service.attachment_file_path(db, attachment_id, user.id)
    return FileResponse(path, filename=attachment.file_name, media_type=attachment.file_type)

