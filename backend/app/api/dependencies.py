"""Authentication and CSRF dependencies for the two isolated entry points."""

from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.security import (
    ADMIN_SESSION_COOKIE,
    USER_SESSION_COOKIE,
    load_session_token,
    validate_csrf,
)
from app.db.session import get_db
from app.models import User
from app.repositories import user_repository
from app.services.setting_service import get_int_setting

DbSession = Annotated[Session, Depends(get_db)]


def current_user(
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=USER_SESSION_COOKIE)] = None,
) -> User:
    """Resolve an active user and enforce session-version revocation."""

    if not token:
        raise AppError(401, "NOT_AUTHENTICATED", "请先登录")
    principal = load_session_token(token, "user")
    user = user_repository.get_by_id(db, principal.subject_id)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise AppError(401, "SESSION_EXPIRED", "会话已失效，请重新登录")
    if user.session_version != principal.session_version:
        raise AppError(401, "SESSION_EXPIRED", "会话已失效，请重新登录")
    return user


def current_admin(
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> bool:
    """Resolve the independent administrator session."""

    if not token:
        raise AppError(401, "NOT_AUTHENTICATED", "请先登录管理员入口")
    principal = load_session_token(token, "admin")
    if principal.session_version != get_int_setting(db, "admin_session_version"):
        raise AppError(401, "SESSION_EXPIRED", "管理员会话已失效")
    return True


def user_csrf(request: Request, _user: Annotated[User, Depends(current_user)]) -> None:
    """Require both a valid normal-user session and CSRF token."""

    validate_csrf(request)


def admin_csrf(request: Request, _admin: Annotated[bool, Depends(current_admin)]) -> None:
    """Require both a valid administrator session and admin CSRF token."""

    validate_csrf(request, admin=True)
