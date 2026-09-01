"""Cookie response helpers shared by normal and administrator auth routes."""

from fastapi import Response

from app.core.config import get_settings
from app.core.security import (
    ADMIN_CSRF_COOKIE,
    ADMIN_SESSION_COOKIE,
    USER_CSRF_COOKIE,
    USER_SESSION_COOKIE,
)


def set_auth_cookies(
    response: Response,
    *,
    session_token: str,
    csrf_token: str,
    admin: bool = False,
) -> None:
    """Set isolated session/CSRF cookie pairs with secure attributes."""

    settings = get_settings()
    session_name = ADMIN_SESSION_COOKIE if admin else USER_SESSION_COOKIE
    csrf_name = ADMIN_CSRF_COOKIE if admin else USER_CSRF_COOKIE
    max_age = settings.admin_session_ttl_seconds if admin else settings.user_session_ttl_seconds
    common = {
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "max_age": max_age,
    }
    response.set_cookie(session_name, session_token, httponly=True, **common)
    response.set_cookie(csrf_name, csrf_token, httponly=False, **common)


def clear_auth_cookies(response: Response, *, admin: bool = False) -> None:
    """Expire the isolated session and CSRF cookie pair."""

    session_name = ADMIN_SESSION_COOKIE if admin else USER_SESSION_COOKIE
    csrf_name = ADMIN_CSRF_COOKIE if admin else USER_CSRF_COOKIE
    response.delete_cookie(session_name, path="/")
    response.delete_cookie(csrf_name, path="/")
