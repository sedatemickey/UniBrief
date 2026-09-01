"""Pydantic schemas for global dictionaries and user-owned sources."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

ShortName = Annotated[str, StringConstraints(min_length=1, max_length=64)]
ExternalId = Annotated[str, StringConstraints(min_length=1, max_length=128)]

Status = Literal["ACTIVE", "DISABLED"]


class PlatformCreate(BaseModel):
    name: ShortName
    type: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    status: Status = "ACTIVE"


class PlatformPatch(BaseModel):
    name: ShortName | None = None
    type: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def require_change(self) -> "PlatformPatch":
        """Validate the declared schema invariant."""

        if self.name is None and self.type is None and self.status is None:
            raise ValueError("至少提供一个要修改的字段")
        return self


class PlatformResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    status: str | None = None
    created_at: datetime | None = None


class PlatformList(BaseModel):
    items: list[PlatformResponse]


class PlatformPage(PlatformList):
    page: int
    page_size: int
    total: int
    total_pages: int


class CategoryCreate(BaseModel):
    name: ShortName
    description: Annotated[str, StringConstraints(max_length=255)] | None = None
    status: Status = "ACTIVE"


class CategoryPatch(BaseModel):
    name: ShortName | None = None
    description: Annotated[str, StringConstraints(max_length=255)] | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def require_change(self) -> "CategoryPatch":
        """Validate the declared schema invariant."""

        if not self.model_fields_set:
            raise ValueError("至少提供一个要修改的字段")
        return self


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    status: str | None = None
    created_at: datetime | None = None


class CategoryList(BaseModel):
    items: list[CategoryResponse]


class CategoryPage(CategoryList):
    page: int
    page_size: int
    total: int
    total_pages: int


class ChannelCreate(BaseModel):
    platform_id: int = Field(gt=0)
    external_id: ExternalId
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    channel_type: Annotated[str, StringConstraints(min_length=1, max_length=32)]


class ChannelPatch(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)] | None = None
    channel_type: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ChannelPatch":
        """Validate the declared schema invariant."""

        if self.name is None and self.channel_type is None:
            raise ValueError("至少提供一个要修改的字段")
        return self


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_id: int
    external_id: str
    name: str
    channel_type: str
    created_at: datetime


class ChannelPage(BaseModel):
    items: list[ChannelResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class SenderCreate(BaseModel):
    platform_id: int = Field(gt=0)
    external_id: ExternalId
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    source_type: Annotated[str, StringConstraints(min_length=1, max_length=32)] = "UNKNOWN"
    credibility: Decimal = Field(
        default=Decimal("0.500"), ge=0, le=1, max_digits=4, decimal_places=3
    )


class SenderPatch(BaseModel):
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=255)] | None = None
    source_type: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    credibility: Decimal | None = Field(default=None, ge=0, le=1, max_digits=4, decimal_places=3)

    @model_validator(mode="after")
    def require_change(self) -> "SenderPatch":
        """Validate the declared schema invariant."""

        if self.display_name is None and self.source_type is None and self.credibility is None:
            raise ValueError("至少提供一个要修改的字段")
        return self


class SenderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_id: int
    external_id: str
    display_name: str
    source_type: str
    credibility: Decimal
    created_at: datetime


class SenderPage(BaseModel):
    items: list[SenderResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
