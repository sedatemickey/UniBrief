"""Pydantic schemas shared by authentication and administration APIs."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    model_validator,
)

Username = Annotated[
    str,
    StringConstraints(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
]
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]


class UserCreate(BaseModel):
    username: Username
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    password: Password


class UserLogin(BaseModel):
    username: Username
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class PasswordChange(BaseModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    new_password: Password


class PasswordReset(BaseModel):
    new_password: Password


class AdminLogin(BaseModel):
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    status: str
    last_login_at: datetime | None = None
    created_at: datetime | None = None

    @field_serializer("last_login_at", "created_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        """Serialize the database UTC timestamp for the API."""

        if value is None:
            return None
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")


class RegistrationStatus(BaseModel):
    enabled: bool


class AdminAuthenticated(BaseModel):
    authenticated: bool = True


class AdminUserPatch(BaseModel):
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    status: Literal["ACTIVE", "DISABLED"] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AdminUserPatch":
        """Validate the declared schema invariant."""

        if self.display_name is None and self.status is None:
            raise ValueError("至少提供一个要修改的字段")
        return self


class RegistrationSettingPatch(BaseModel):
    enabled: bool


class AdminSettingsResponse(BaseModel):
    registration_enabled: bool
    admin_password_configured: bool


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class UserPage(BaseModel):
    items: list[UserResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
