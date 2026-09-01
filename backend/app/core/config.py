"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Validated runtime settings for the UniBrief backend."""

    model_config = SettingsConfigDict(
        env_file=(_REPOSITORY_ROOT / ".env", _REPOSITORY_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:5173"
    trusted_origins: str = "http://localhost:5173"

    database_url: str = Field(
        default="mysql+pymysql://unibrief:change-me@127.0.0.1:3306/unibrief?charset=utf8mb4"
    )
    test_database_url: str | None = None

    user_session_secret: str = "replace-with-at-least-32-random-bytes"
    admin_session_secret: str = "replace-with-a-different-random-secret"
    user_session_ttl_seconds: int = Field(default=604800, gt=0)
    admin_session_ttl_seconds: int = Field(default=28800, gt=0)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    attachment_storage_dir: Path = Path("./var/attachments")
    attachment_max_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    attachment_timeout_seconds: int = Field(default=30, gt=0)
    attachment_max_retries: int = Field(default=2, ge=0)
    attachment_max_redirects: int = Field(default=3, ge=0)
    attachment_downloading_stale_seconds: int = Field(default=600, gt=0)

    reminder_scan_interval_seconds: int = Field(default=60, gt=0)
    event_status_scan_interval_seconds: int = Field(default=60, gt=0)

    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_default_model: str = ""
    ai_timeout_seconds: int = Field(default=60, gt=0)
    ai_max_retries: int = Field(default=2, ge=0)
    ai_temperature: float = Field(default=0.1, ge=0, le=2)
    ai_json_mode: Literal["auto", "always", "off"] = "auto"
    ai_batch_poll_seconds: int = Field(default=30, gt=0)
    ai_batch_size_threshold: int = Field(default=20, gt=0)
    ai_batch_max_wait_seconds: int = Field(default=300, gt=0)
    ai_processing_stale_seconds: int = Field(default=600, gt=0)

    napcat_enabled: bool = False
    napcat_ws_url: str = "ws://127.0.0.1:3001"
    napcat_access_token: str = ""
    napcat_reconnect_max_seconds: int = Field(default=30, gt=0)
    napcat_heartbeat_timeout_seconds: int = Field(default=90, gt=0)
    napcat_import_batch_size: int = Field(default=20, ge=1, le=1000)
    napcat_import_flush_seconds: int = Field(default=5, gt=0)
    unibrief_base_url: str = "http://127.0.0.1:8000"
    unibrief_username: str = ""
    unibrief_password: str = ""

    @field_validator("ai_base_url")
    @classmethod
    def validate_ai_base_url(cls, value: str) -> str:
        """Require an HTTP(S) API root and normalize its trailing slash."""

        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("AI_BASE_URL must use http:// or https://")
        return normalized
    @model_validator(mode="after")
    def validate_security_contract(self) -> "Settings":
        """Reject secret reuse, production placeholders, and invalid enabled bridges."""

        if self.user_session_secret == self.admin_session_secret:
            raise ValueError("USER_SESSION_SECRET and ADMIN_SESSION_SECRET must differ")
        placeholders = {
            "replace-with-at-least-32-random-bytes",
            "replace-with-a-different-random-secret",
        }
        if self.app_env == "production" and (
            self.user_session_secret in placeholders or self.admin_session_secret in placeholders
        ):
            raise ValueError("Production session secrets must not use placeholder values")
        if self.napcat_enabled:
            if not self.napcat_ws_url.startswith(("ws://", "wss://")):
                raise ValueError("NAPCAT_WS_URL must use ws:// or wss://")
            if not self.unibrief_username:
                raise ValueError("UNIBRIEF_USERNAME is required when NAPCAT_ENABLED=true")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings instance."""

    return Settings()

