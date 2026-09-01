"""Schemas for Information, Tag, Event, Reminder, and provenance APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.enums import InformationStatus, RelationType

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class NamedResource(BaseModel):
    id: int
    name: str


class InformationEventSummary(BaseModel):
    id: int
    start_at: datetime | None
    deadline: datetime | None
    event_status: str

    @field_serializer("start_at", "deadline", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        """Serialize database UTC values with an explicit offset."""

        return _utc_iso(value)


class InformationSummary(BaseModel):
    id: int
    title: str
    summary: str
    source_type: str
    importance: int
    confidence: float
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    categories: list[NamedResource]
    tags: list[NamedResource]
    event: InformationEventSummary | None

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_utc(self, value: datetime) -> str:
        """Serialize database UTC values with an explicit offset."""

        return _utc_iso(value) or ""


class InformationPage(BaseModel):
    items: list[InformationSummary]
    page: int
    page_size: int
    total: int
    total_pages: int


class InformationSource(BaseModel):
    message_id: int
    relation_type: str
    content: str
    sent_at: datetime
    channel_name: str
    sender_display_name: str

    @field_serializer("sent_at", when_used="json")
    def serialize_sent_at(self, value: datetime) -> str:
        """Serialize source-message time as UTC."""

        return _utc_iso(value) or ""


class ReminderSummary(BaseModel):
    id: int
    remind_at: datetime
    reminder_status: str
    is_custom_time: bool
    triggered_at: datetime | None
    read_at: datetime | None

    @field_serializer("remind_at", "triggered_at", "read_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        """Serialize reminder timestamps as UTC."""

        return _utc_iso(value)


class InformationDetail(InformationSummary):
    reminder: ReminderSummary | None
    sources: list[InformationSource]


class InformationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, min_length=1, max_length=8000)
    importance: int | None = Field(default=None, ge=1, le=5)
    status: InformationStatus | None = None
    category_ids: list[int] | None = Field(default=None, max_length=50)
    tag_names: list[Name] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_patch(self) -> InformationPatch:
        """Require one change and reject explicit null for non-null scalar fields."""

        changed = self.model_fields_set - {"expected_version"}
        if not changed:
            raise ValueError("at least one field must be changed")
        for field in ("title", "summary", "importance", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if self.category_ids is not None and len(self.category_ids) != len(set(self.category_ids)):
            raise ValueError("category_ids must be unique")
        return self


class LinkMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relation_type: RelationType


class MessageInformationResponse(BaseModel):
    message_id: int
    information_id: int
    relation_type: str


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name


class TagPatch(TagCreate):
    pass


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime

    @field_serializer("created_at", when_used="json")
    def serialize_created(self, value: datetime) -> str:
        """Serialize Tag creation time as UTC."""

        return _utc_iso(value) or ""


class TagPage(BaseModel):
    items: list[TagResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class PopularTag(BaseModel):
    id: int
    name: str
    usage_count: int


class EventListItem(BaseModel):
    id: int
    information_id: int
    information_version: int
    title: str
    importance: int
    start_at: datetime | None
    deadline: datetime | None
    event_status: str
    updated_at: datetime

    @field_serializer("start_at", "deadline", "updated_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        """Serialize Event timestamps as UTC."""

        return _utc_iso(value)


class EventPage(BaseModel):
    items: list[EventListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class EventDetail(EventListItem):
    summary: str
    reminder: ReminderSummary | None


class EventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_information_version: int = Field(ge=1)
    start_at: datetime | None = None
    deadline: datetime | None = None
    event_status: Literal["UPCOMING", "COMPLETED", "CANCELLED"] | None = None

    @field_validator("start_at", "deadline")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware values when an Event time is supplied."""

        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("event time must include timezone")
        return value

    @model_validator(mode="after")
    def require_change(self) -> EventPatch:
        """Require at least one Event field beyond the optimistic version."""

        if not (self.model_fields_set - {"expected_information_version"}):
            raise ValueError("at least one field must be changed")
        return self


class ReminderListItem(ReminderSummary):
    event_id: int
    information_id: int
    title: str
    deadline: datetime | None

    @field_serializer("deadline", when_used="json")
    def serialize_deadline(self, value: datetime | None) -> str | None:
        """Serialize parent Event deadline as UTC."""

        return _utc_iso(value)


class ReminderPage(BaseModel):
    items: list[ReminderListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class ReminderPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remind_at: datetime | None = None
    enabled: bool | None = None

    @field_validator("remind_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Require a timezone-aware custom reminder timestamp."""

        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("remind_at must include timezone")
        return value

    @model_validator(mode="after")
    def require_change(self) -> ReminderPatch:
        """Require an explicit time or enabled flag."""

        if not self.model_fields_set:
            raise ValueError("at least one field must be changed")
        if "remind_at" in self.model_fields_set and self.remind_at is None:
            raise ValueError("remind_at cannot be null")
        return self


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")
