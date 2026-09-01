"""Strict request, provider, and analysis result schemas for Phase 2."""

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

from app.core.enums import RelationType

ModelId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class AIEventOutput(BaseModel):
    """Validated event proposed by the provider."""

    model_config = ConfigDict(extra="forbid")

    start_at: datetime | None = None
    deadline: datetime | None = None
    status: Literal["UPCOMING"] = "UPCOMING"

    @field_validator("start_at", "deadline")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware provider timestamps and normalize them to UTC."""

        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_time_range(self) -> AIEventOutput:
        """Require at least one event time and a non-negative interval."""

        if self.start_at is None and self.deadline is None:
            raise ValueError("event requires start_at or deadline")
        if self.start_at is not None and self.deadline is not None:
            if self.deadline < self.start_at:
                raise ValueError("event deadline must not be earlier than start_at")
        return self


class AIInformationOutput(BaseModel):
    """One create/link/update/correct decision emitted for a Message."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["create", "link", "update", "correct"]
    target_information_id: int | None = Field(default=None, ge=1)
    relation_type: RelationType
    title: ShortText
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
    source_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
    ]
    importance: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    categories: list[ShortText] = Field(default_factory=list, max_length=20)
    tags: list[ShortText] = Field(default_factory=list, max_length=30)
    event: AIEventOutput | None = None

    @field_validator("categories", "tags")
    @classmethod
    def normalize_names(cls, value: list[str]) -> list[str]:
        """Remove duplicate names while preserving provider order."""

        result: list[str] = []
        seen: set[str] = set()
        for name in value:
            key = name.casefold()
            if key not in seen:
                seen.add(key)
                result.append(name)
        return result

    @model_validator(mode="after")
    def validate_action_matrix(self) -> AIInformationOutput:
        """Enforce the documented action/target/relation compatibility table."""

        expected = {
            "create": (None, RelationType.CREATE),
            "link": ("target", RelationType.SUPPORT),
            "update": ("target", RelationType.UPDATE),
            "correct": ("target", RelationType.CORRECTION),
        }
        target_rule, relation = expected[self.action]
        if target_rule is None and self.target_information_id is not None:
            raise ValueError("create requires target_information_id=null")
        if target_rule == "target" and self.target_information_id is None:
            raise ValueError(f"{self.action} requires target_information_id")
        if self.relation_type != relation:
            raise ValueError(f"{self.action} requires relation_type={relation.value}")
        return self


class AIMessageOutput(BaseModel):
    """Strict top-level provider result for one Message."""

    model_config = ConfigDict(extra="forbid")

    useful: bool
    items: list[AIInformationOutput] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_usefulness(self) -> AIMessageOutput:
        """Keep useful and item cardinality logically consistent."""

        if self.useful and not self.items:
            raise ValueError("useful=true requires at least one item")
        if not self.useful and self.items:
            raise ValueError("useful=false requires items=[]")
        targets = [item.target_information_id for item in self.items if item.target_information_id]
        if len(targets) != len(set(targets)):
            raise ValueError("one result cannot write the same target more than once")
        return self


class AIConfigResponse(BaseModel):
    base_url: str
    default_model: str
    timeout_seconds: int
    max_retries: int
    has_api_key: bool


class AIModelSummary(BaseModel):
    id: str


class AIModelsResponse(BaseModel):
    supports_listing: bool
    models: list[AIModelSummary]
    error_code: str | None = None
    message: str | None = None


class AITestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: ModelId | None = None
    mode: Literal["retry"] = "retry"


class AITestResponse(BaseModel):
    ok: bool = True
    model: str
    latency_ms: int
    message: str = "连接成功"


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: ModelId | None = None
    mode: Literal["retry", "compare"] = "retry"


class AnalyzeResponse(BaseModel):
    message_id: int
    process_status: str
    analysis_id: int
    model_name: str
    useful: bool
    information_ids: list[int] = Field(default_factory=list)
    business_applied: bool = True


class AnalyzeBatchRequest(AnalyzeRequest):
    message_ids: list[int] = Field(min_length=1, max_length=100)

    @field_validator("message_ids")
    @classmethod
    def require_unique_ids(cls, value: list[int]) -> list[int]:
        """Reject ambiguous duplicate Message IDs in a manual batch."""

        if any(item < 1 for item in value):
            raise ValueError("message_ids must be positive")
        if len(value) != len(set(value)):
            raise ValueError("message_ids must be unique")
        return value


class BatchItemError(BaseModel):
    code: str
    retryable: bool
    message: str | None = None


class AnalyzeBatchItemResponse(BaseModel):
    message_id: int
    status: str
    analysis_id: int | None
    business_applied: bool
    information_ids: list[int] = Field(default_factory=list)
    error: BatchItemError | None = None


class AnalyzeBatchResponse(BaseModel):
    mode: Literal["retry", "compare"]
    results: list[AnalyzeBatchItemResponse]


class CandidateInformation(BaseModel):
    """Compact current-user candidate snapshot included in the provider prompt."""

    id: int
    version: int
    title: str
    summary: str
    importance: int
    categories: list[str]
    tags: list[str]
    event_start_at: datetime | None = None
    event_deadline: datetime | None = None

    @field_serializer("event_start_at", "event_deadline", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        """Serialize MySQL UTC DATETIME values unambiguously."""

        if value is None:
            return None
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")

