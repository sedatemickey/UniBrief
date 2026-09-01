"""Normal-user authentication business logic and transaction boundaries."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories import user_repository
from app.schemas.auth import PasswordChange, UserCreate
from app.services.setting_service import get_bool_setting


def register_user(db: Session, payload: UserCreate) -> User:
    """Create an enabled user when registration is open."""

    if not get_bool_setting(db, "registration_enabled"):
        raise AppError(400, "REGISTRATION_DISABLED", "当前未开放注册")
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


def authenticate_user(db: Session, username: str, password: str) -> User:
    """Authenticate without disclosing whether a username exists or is disabled."""

    user = user_repository.get_by_username(db, username)
    if (
        user is None
        or user.status != UserStatus.ACTIVE.value
        or not verify_password(user.password_hash, password)
    ):
        raise AppError(401, "NOT_AUTHENTICATED", "用户名或密码错误")
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(user)
    return user


def change_user_password(db: Session, user: User, payload: PasswordChange) -> None:
    """Change a user's password and revoke all existing sessions."""

    if not verify_password(user.password_hash, payload.current_password):
        raise AppError(401, "NOT_AUTHENTICATED", "当前密码错误")
    user.password_hash = hash_password(payload.new_password)
    user.session_version += 1
    db.commit()
