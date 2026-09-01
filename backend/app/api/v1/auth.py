"""Normal-user authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.cookies import clear_auth_cookies, set_auth_cookies
from app.api.dependencies import DbSession, current_user, user_csrf
from app.core.security import (
    SessionPrincipal,
    create_session_token,
    new_csrf_token,
    validate_request_origin,
)
from app.models import User
from app.schemas.auth import (
    PasswordChange,
    RegistrationStatus,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import authenticate_user, change_user_password, register_user
from app.services.setting_service import get_bool_setting

router = APIRouter(prefix="/auth", tags=["auth"])


def _establish_user_session(response: Response, user: User) -> None:
    principal = SessionPrincipal("user", user.id, user.session_version)
    set_auth_cookies(
        response,
        session_token=create_session_token(principal),
        csrf_token=new_csrf_token(),
    )


@router.get("/registration-status", response_model=RegistrationStatus)
def registration_status(db: DbSession) -> RegistrationStatus:
    """Return whether public self-registration is currently enabled."""

    return RegistrationStatus(enabled=get_bool_setting(db, "registration_enabled"))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, response: Response, db: DbSession) -> User:
    """Register and sign in a user when the administrator enabled registration."""

    validate_request_origin(request)
    user = register_user(db, payload)
    _establish_user_session(response, user)
    return user


@router.post("/login", response_model=UserResponse)
def login(payload: UserLogin, request: Request, response: Response, db: DbSession) -> User:
    """Authenticate a normal user and rotate both auth cookies."""

    validate_request_origin(request)
    user = authenticate_user(db, payload.username, payload.password)
    _establish_user_session(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    _csrf: Annotated[None, Depends(user_csrf)],
) -> None:
    """Clear the normal-user session and CSRF cookies."""

    clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    """Return the current normal user's safe profile."""

    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChange,
    response: Response,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> None:
    """Change the current password, revoke sessions, and clear cookies."""

    change_user_password(db, user, payload)
    clear_auth_cookies(response)
