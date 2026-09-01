"""Schemas for message ingestion, querying, and attachment metadata."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

ExternalId191 = Annotated[str, StringConstraints(min_length=1, max_length=191)]


class ImportPlatform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    type: Annotated[str, StringConstraints(min_length=1, max_length=32)]


class ImportChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    channel_type: Annotated[str, StringConstraints(min_length=1, max_length=32)]


class ImportSender(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    source_type: Annotated[str, StringConstraints(min_length=1, max_length=32)] = "UNKNOWN"


class ImportAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: ExternalId191 | None = None
    file_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    file_type: Annotated[str, StringConstraints(max_length=64)] | None = None
    file_url: Annotated[str, StringConstraints(min_length=1, max_length=1024)]

    @field_validator("file_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        """Validate the declared schema invariant."""

        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("附件 URL 仅允许 HTTP/HTTPS")
        return value


class MessageImportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: ExternalId191
    sender: ImportSender
    content: str = Field(max_length=65535)
    sent_at: datetime
    attachments: list[ImportAttachment] = Field(default_factory=list, max_length=100)

    @field_validator("sent_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Validate the declared schema invariant."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sent_at 必须包含时区")
        return value

    @model_validator(mode="after")
    def require_content_or_attachment(self) -> "MessageImportItem":
        """Validate the declared schema invariant."""

        if not self.content and not self.attachments:
            raise ValueError("消息正文和附件不能同时为空")
        return self


class MessageImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: ImportPlatform
    channel: ImportChannel
    messages: list[Any] = Field(min_length=1, max_length=1000)


class ImportItemError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ImportItemResult(BaseModel):
    external_id: str
    status: Literal["INSERTED", "DUPLICATE", "FAILED"]
    message_id: int | None = None
    error: ImportItemError | None = None


class MessageImportResponse(BaseModel):
    received: int
    inserted: int
    duplicates: int
    failed: int
    attachment_metadata_created: int
    attachment_downloads_scheduled: int
    results: list[ImportItemResult]


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    file_name: str
    file_type: str | None
    file_size: int | None
    sha256: str | None
    download_status: str
    download_attempts: int
    downloaded_at: datetime | None
    last_error: str | None


class AttachmentRetryResponse(BaseModel):
    id: int
    download_status: str
    scheduled: bool = True


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    sender_id: int
    external_id: str
    content: str
    sent_at: datetime
    ingested_at: datetime
    process_status: str
    processing_started_at: datetime | None

    @field_serializer("sent_at", "ingested_at", "processing_started_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        """Serialize the database UTC timestamp for the API."""

        if value is None:
            return None
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")


class MessagePage(BaseModel):
    items: list[MessageResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class AIAnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_name: str
    status: str
    useful: bool | None
    error_code: str | None
    error_message: str | None
    latency_ms: int | None
    analyzed_at: datetime


class MessageDetail(MessageResponse):
    platform_id: int
    channel_name: str
    sender_display_name: str
    attachments: list[AttachmentResponse]
    analyses: list[AIAnalysisSummary]
