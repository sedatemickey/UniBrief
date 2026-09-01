"""Password hashing, signed sessions, CSRF tokens, and origin checks."""

from dataclasses import dataclass
from hmac import compare_digest
from secrets import token_urlsafe
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import Settings, get_settings
from app.core.errors import AppError

USER_SESSION_COOKIE = "unibrief_session"
USER_CSRF_COOKIE = "unibrief_csrf"
ADMIN_SESSION_COOKIE = "unibrief_admin_session"
ADMIN_CSRF_COOKIE = "unibrief_admin_csrf"

_password_hasher = PasswordHasher()


@dataclass(frozen=True)
class SessionPrincipal:
    """Identity and revocation version recovered from a signed cookie."""

    subject_type: Literal["user", "admin"]
    subject_id: int | None
    session_version: int


def hash_password(password: str) -> str:
    """Hash a password using Argon2id with the library's safe defaults."""

    return _password_hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    """Verify a password without exposing hash parsing errors."""

    try:
        return _password_hasher.verify(password_hash, candidate)
    except (VerificationError, InvalidHashError):
        return False


def new_csrf_token() -> str:
    """Generate a high-entropy double-submit CSRF token."""

    return token_urlsafe(32)


def _serializer(
    subject_type: Literal["user", "admin"], settings: Settings
) -> URLSafeTimedSerializer:
    secret = (
        settings.user_session_secret if subject_type == "user" else settings.admin_session_secret
    )
    return URLSafeTimedSerializer(secret, salt=f"unibrief-{subject_type}-session-v1")


def create_session_token(principal: SessionPrincipal, settings: Settings | None = None) -> str:
    """Create a signed, timestamped session token."""

    active_settings = settings or get_settings()
    return _serializer(principal.subject_type, active_settings).dumps(
        {
            "type": principal.subject_type,
            "id": principal.subject_id,
            "version": principal.session_version,
        }
    )


def load_session_token(
    token: str,
    subject_type: Literal["user", "admin"],
    settings: Settings | None = None,
) -> SessionPrincipal:
    """Validate a session token and return its typed principal."""

    active_settings = settings or get_settings()
    max_age = (
        active_settings.user_session_ttl_seconds
        if subject_type == "user"
        else active_settings.admin_session_ttl_seconds
    )
    try:
        payload = _serializer(subject_type, active_settings).loads(token, max_age=max_age)
    except SignatureExpired as exc:
        raise AppError(401, "SESSION_EXPIRED", "会话已过期，请重新登录") from exc
    except BadSignature as exc:
        raise AppError(401, "NOT_AUTHENTICATED", "请先登录") from exc
    if payload.get("type") != subject_type:
        raise AppError(401, "NOT_AUTHENTICATED", "请先登录")
    subject_id = payload.get("id")
    version = payload.get("version")
    if subject_type == "user" and not isinstance(subject_id, int):
        raise AppError(401, "NOT_AUTHENTICATED", "请先登录")
    if not isinstance(version, int):
        raise AppError(401, "NOT_AUTHENTICATED", "请先登录")
    return SessionPrincipal(subject_type, subject_id, version)


def validate_csrf(request: Request, *, admin: bool = False) -> None:
    """Validate the matching double-submit cookie and request header."""

    cookie_name = ADMIN_CSRF_COOKIE if admin else USER_CSRF_COOKIE
    header_name = "X-Admin-CSRF-Token" if admin else "X-CSRF-Token"
    cookie_value = request.cookies.get(cookie_name)
    header_value = request.headers.get(header_name)
    if not cookie_value or not header_value or not compare_digest(cookie_value, header_value):
        raise AppError(403, "CSRF_FAILED", "CSRF 校验失败")


def validate_request_origin(request: Request) -> None:
    """Reject browser-originated authentication requests from untrusted origins."""

    origin = request.headers.get("origin")
    if not origin:
        return
    trusted = {item.strip().rstrip("/") for item in get_settings().trusted_origins.split(",")}
    if origin.rstrip("/") not in trusted:
        raise AppError(403, "CSRF_FAILED", "请求来源不受信任")
