"""Independent administrator authentication and account-management routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.cookies import clear_auth_cookies, set_auth_cookies
from app.api.dependencies import DbSession, admin_csrf, current_admin
from app.core.security import (
    SessionPrincipal,
    create_session_token,
    new_csrf_token,
    validate_request_origin,
)
from app.models import User
from app.schemas.auth import (
    AdminAuthenticated,
    AdminLogin,
    AdminSettingsResponse,
    AdminUserPatch,
    PasswordChange,
    PasswordReset,
    RegistrationSettingPatch,
    RegistrationStatus,
    UserCreate,
    UserPage,
    UserResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/auth/login", response_model=AdminAuthenticated)
def login(
    payload: AdminLogin, request: Request, response: Response, db: DbSession
) -> AdminAuthenticated:
    """Authenticate the independent administrator principal."""

    validate_request_origin(request)
    version = admin_service.authenticate_admin(db, payload.password)
    principal = SessionPrincipal("admin", None, version)
    set_auth_cookies(
        response,
        session_token=create_session_token(principal),
        csrf_token=new_csrf_token(),
        admin=True,
    )
    return AdminAuthenticated()


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> None:
    """Clear only administrator cookies."""

    clear_auth_cookies(response, admin=True)


@router.get("/auth/me", response_model=AdminAuthenticated)
def me(_admin: Annotated[bool, Depends(current_admin)]) -> AdminAuthenticated:
    """Confirm that the administrator session remains valid."""

    return AdminAuthenticated()


@router.post("/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChange,
    response: Response,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> None:
    """Change administrator password, revoke sessions, and clear cookies."""

    admin_service.change_admin_password(db, payload)
    clear_auth_cookies(response, admin=True)


@router.get("/users", response_model=UserPage)
def users(
    db: DbSession,
    _admin: Annotated[bool, Depends(current_admin)],
    keyword: str | None = None,
    user_status: Annotated[Literal["ACTIVE", "DISABLED"] | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["created_at_desc", "username_asc"] = "created_at_desc",
) -> UserPage:
    """List normal accounts without reading private business content."""

    items, total, total_pages = admin_service.list_users(
        db,
        keyword=keyword,
        status=user_status,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    return UserPage(
        items=[UserResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> User:
    """Create a normal account without generating or returning a plaintext password."""

    return admin_service.create_user(db, payload)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: AdminUserPatch,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> User:
    """Update or disable a normal account."""

    return admin_service.update_user(db, user_id, payload)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: PasswordReset,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> None:
    """Set the supplied password hash and revoke the user's existing sessions."""

    admin_service.reset_user_password(db, user_id, payload.new_password)


@router.get("/settings", response_model=AdminSettingsResponse)
def settings(
    db: DbSession, _admin: Annotated[bool, Depends(current_admin)]
) -> AdminSettingsResponse:
    """Return safe setting summaries without secret values."""

    return AdminSettingsResponse(**admin_service.get_safe_settings(db))


@router.patch("/settings/registration", response_model=RegistrationStatus)
def set_registration(
    payload: RegistrationSettingPatch,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> RegistrationStatus:
    """Enable or disable public registration through the setting whitelist."""

    return RegistrationStatus(enabled=admin_service.set_registration_enabled(db, payload.enabled))
