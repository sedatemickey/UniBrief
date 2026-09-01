"""Integration tests for isolated user/admin cookie sessions and setting controls."""

from fastapi.testclient import TestClient

from app.core.security import (
    ADMIN_CSRF_COOKIE,
    ADMIN_SESSION_COOKIE,
    USER_CSRF_COOKIE,
    USER_SESSION_COOKIE,
    hash_password,
)
from app.db.session import SessionLocal
from app.main import app
from app.services.setting_service import set_setting


def _enable_registration() -> None:
    with SessionLocal() as db:
        set_setting(db, "registration_enabled", True)
        db.commit()


def _initialize_admin(password: str = "AdminPass123") -> None:
    with SessionLocal() as db:
        set_setting(db, "admin_password_hash", hash_password(password))
        db.commit()


def test_registration_default_closed_then_cookie_session_and_revocation() -> None:
    client = TestClient(app)
    payload = {
        "username": "student01",
        "display_name": "学生一",
        "password": "ExamplePass123",
    }

    closed = client.post("/api/v1/auth/register", json=payload)
    assert closed.status_code == 400
    assert closed.json()["error"]["code"] == "REGISTRATION_DISABLED"

    _enable_registration()
    registered = client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 201
    assert registered.json()["username"] == "student01"
    assert client.cookies.get(USER_SESSION_COOKIE)
    csrf = client.cookies.get(USER_CSRF_COOKIE)
    assert csrf
    assert "HttpOnly" in registered.headers.get("set-cookie", "")

    assert client.get("/api/v1/auth/me").status_code == 200
    missing_csrf = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "ExamplePass123", "new_password": "ChangedPass123"},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_FAILED"

    old_session = client.cookies.get(USER_SESSION_COOKIE)
    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": "ExamplePass123", "new_password": "ChangedPass123"},
    )
    assert changed.status_code == 204
    client.cookies.set(USER_SESSION_COOKIE, old_session)
    expired = client.get("/api/v1/auth/me")
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "SESSION_EXPIRED"


def test_admin_uninitialized_and_independent_user_management_session() -> None:
    client = TestClient(app)
    uninitialized = client.post("/api/v1/admin/auth/login", json={"password": "AdminPass123"})
    assert uninitialized.status_code == 503
    assert uninitialized.json()["error"]["code"] == "ADMIN_NOT_INITIALIZED"

    _initialize_admin()
    logged_in = client.post("/api/v1/admin/auth/login", json={"password": "AdminPass123"})
    assert logged_in.status_code == 200
    assert client.cookies.get(ADMIN_SESSION_COOKIE)
    assert not client.cookies.get(USER_SESSION_COOKIE)
    admin_csrf = client.cookies.get(ADMIN_CSRF_COOKIE)
    assert admin_csrf

    safe_settings = client.get("/api/v1/admin/settings")
    assert safe_settings.status_code == 200
    assert safe_settings.json() == {
        "registration_enabled": False,
        "admin_password_configured": True,
    }
    assert "password_hash" not in safe_settings.text

    user_payload = {
        "username": "student02",
        "display_name": "学生二",
        "password": "ExamplePass123",
    }
    assert client.post("/api/v1/admin/users", json=user_payload).status_code == 403
    created = client.post(
        "/api/v1/admin/users",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json=user_payload,
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    listed = client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    disabled = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"status": "DISABLED"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"

    user_client = TestClient(app)
    rejected = user_client.post(
        "/api/v1/auth/login",
        json={"username": "student02", "password": "ExamplePass123"},
    )
    assert rejected.status_code == 401


def test_registration_toggle_password_resets_and_admin_session_revocation() -> None:
    client = TestClient(app)
    _initialize_admin()
    assert (
        client.post("/api/v1/admin/auth/login", json={"password": "AdminPass123"}).status_code
        == 200
    )
    admin_csrf = client.cookies.get(ADMIN_CSRF_COOKIE)
    old_admin_session = client.cookies.get(ADMIN_SESSION_COOKIE)
    enabled = client.patch(
        "/api/v1/admin/settings/registration",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json() == {"enabled": True}

    user_client = TestClient(app)
    registered = user_client.post(
        "/api/v1/auth/register",
        json={
            "username": "reset_user",
            "display_name": "重置测试用户",
            "password": "OriginalPass123",
        },
    )
    assert registered.status_code == 201
    user_id = registered.json()["id"]
    reset = client.post(
        f"/api/v1/admin/users/{user_id}/reset-password",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"new_password": "ReplacementPass123"},
    )
    assert reset.status_code == 204
    expired = user_client.get("/api/v1/auth/me")
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "SESSION_EXPIRED"
    assert (
        TestClient(app)
        .post(
            "/api/v1/auth/login",
            json={"username": "reset_user", "password": "OriginalPass123"},
        )
        .status_code
        == 401
    )
    assert (
        TestClient(app)
        .post(
            "/api/v1/auth/login",
            json={"username": "reset_user", "password": "ReplacementPass123"},
        )
        .status_code
        == 200
    )

    changed = client.post(
        "/api/v1/admin/auth/change-password",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"current_password": "AdminPass123", "new_password": "NewAdminPass123"},
    )
    assert changed.status_code == 204
    client.cookies.set(ADMIN_SESSION_COOKIE, old_admin_session)
    revoked = client.get("/api/v1/admin/auth/me")
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "SESSION_EXPIRED"
    assert (
        TestClient(app)
        .post("/api/v1/admin/auth/login", json={"password": "NewAdminPass123"})
        .status_code
        == 200
    )


def test_authentication_rejects_untrusted_browser_origin() -> None:
    _initialize_admin()
    response = TestClient(app).post(
        "/api/v1/admin/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"password": "AdminPass123"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"
