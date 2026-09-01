"""Administrator authentication and user-management business logic."""

from math import ceil

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories import user_repository
from app.schemas.auth import AdminUserPatch, PasswordChange, UserCreate
from app.services.setting_service import (
    get_bool_setting,
    get_int_setting,
    get_raw_setting,
    set_setting,
)


def authenticate_admin(db: Session, password: str) -> int:
    """Validate the configured administrator password and return its session version."""

    password_row = get_raw_setting(db, "admin_password_hash")
    if password_row is None:
        raise AppError(503, "ADMIN_NOT_INITIALIZED", "管理员密码尚未初始化")
    if not verify_password(password_row.value_text, password):
        raise AppError(401, "NOT_AUTHENTICATED", "管理员密码错误")
    return get_int_setting(db, "admin_session_version")


def change_admin_password(db: Session, payload: PasswordChange) -> None:
    """Change the administrator password and revoke existing admin sessions."""

    password_row = get_raw_setting(db, "admin_password_hash")
    if password_row is None:
        raise AppError(503, "ADMIN_NOT_INITIALIZED", "管理员密码尚未初始化")
    if not verify_password(password_row.value_text, payload.current_password):
        raise AppError(401, "NOT_AUTHENTICATED", "当前管理员密码错误")
    set_setting(db, "admin_password_hash", hash_password(payload.new_password))
    set_setting(db, "admin_session_version", get_int_setting(db, "admin_session_version") + 1)
    db.commit()


def create_user(db: Session, payload: UserCreate) -> User:
    """Create a normal user from the administrator entry point."""

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    user_repository.add(db, user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "USERNAME_CONFLICT", "用户名已存在") from exc
    db.refresh(user)
    return user


def list_users(
    db: Session,
    *,
    keyword: str | None,
    status: str | None,
    page: int,
    page_size: int,
    sort: str,
) -> tuple[list[User], int, int]:
    """List users without exposing private-data counts."""

    items, total = user_repository.list_page(
        db,
        keyword=keyword,
        status=status,
        offset=(page - 1) * page_size,
        limit=page_size,
        sort=sort,
    )
    return items, total, ceil(total / page_size) if total else 0


def get_user_or_404(db: Session, user_id: int) -> User:
    """Load a normal user or return the shared not-found response."""

    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    return user


def update_user(db: Session, user_id: int, payload: AdminUserPatch) -> User:
    """Update display/status and revoke sessions when disabling a user."""

    user = get_user_or_404(db, user_id)
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.status is not None and payload.status != user.status:
        user.status = payload.status
        if payload.status == UserStatus.DISABLED.value:
            user.session_version += 1
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(db: Session, user_id: int, new_password: str) -> None:
    """Replace a user password and revoke every existing session."""

    user = get_user_or_404(db, user_id)
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    db.commit()


def get_safe_settings(db: Session) -> dict[str, bool]:
    """Return only non-secret administrator setting summaries."""

    return {
        "registration_enabled": get_bool_setting(db, "registration_enabled"),
        "admin_password_configured": get_raw_setting(db, "admin_password_hash") is not None,
    }


def set_registration_enabled(db: Session, enabled: bool) -> bool:
    """Update the registered public-registration flag."""

    set_setting(db, "registration_enabled", enabled)
    db.commit()
    return enabled
