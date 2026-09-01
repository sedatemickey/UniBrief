"""Integration tests for global dictionaries and per-user source isolation."""

from fastapi.testclient import TestClient

from app.core.security import ADMIN_CSRF_COOKIE, USER_CSRF_COOKIE, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.services.setting_service import set_setting


def _admin_client() -> tuple[TestClient, str]:
    with SessionLocal() as db:
        set_setting(db, "admin_password_hash", hash_password("AdminPass123"))
        db.commit()
    client = TestClient(app)
    response = client.post("/api/v1/admin/auth/login", json={"password": "AdminPass123"})
    assert response.status_code == 200
    csrf = client.cookies.get(ADMIN_CSRF_COOKIE)
    assert csrf
    return client, csrf


def _create_user(admin: TestClient, csrf: str, username: str) -> None:
    response = admin.post(
        "/api/v1/admin/users",
        headers={"X-Admin-CSRF-Token": csrf},
        json={
            "username": username,
            "display_name": username,
            "password": "ExamplePass123",
        },
    )
    assert response.status_code == 201


def _user_client(username: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "ExamplePass123"},
    )
    assert response.status_code == 200
    csrf = client.cookies.get(USER_CSRF_COOKIE)
    assert csrf
    return client, csrf


def test_admin_dictionaries_and_private_source_isolation() -> None:
    admin, admin_csrf = _admin_client()
    platform_response = admin.post(
        "/api/v1/admin/platforms",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"name": "QQ", "type": "IM", "status": "ACTIVE"},
    )
    assert platform_response.status_code == 201
    platform_id = platform_response.json()["id"]

    category_response = admin.post(
        "/api/v1/admin/categories",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"name": "奖学金", "description": "奖学金与资助信息"},
    )
    assert category_response.status_code == 201

    _create_user(admin, admin_csrf, "user_a")
    _create_user(admin, admin_csrf, "user_b")
    user_a, csrf_a = _user_client("user_a")
    user_b, csrf_b = _user_client("user_b")

    public_platforms = user_a.get("/api/v1/platforms")
    assert public_platforms.status_code == 200
    assert [item["name"] for item in public_platforms.json()["items"]] == ["QQ"]
    assert "奖学金" in {item["name"] for item in user_a.get("/api/v1/categories").json()["items"]}

    channel_payload = {
        "platform_id": platform_id,
        "external_id": "group-123",
        "name": "数据库课程群",
        "channel_type": "GROUP",
    }
    created_channel = user_a.post(
        "/api/v1/channels",
        headers={"X-CSRF-Token": csrf_a},
        json=channel_payload,
    )
    assert created_channel.status_code == 201
    channel_id = created_channel.json()["id"]
    duplicate = user_a.post(
        "/api/v1/channels",
        headers={"X-CSRF-Token": csrf_a},
        json=channel_payload,
    )
    assert duplicate.status_code == 200
    conflict_payload = {**channel_payload, "name": "伪造的新名称"}
    conflict = user_a.post(
        "/api/v1/channels",
        headers={"X-CSRF-Token": csrf_a},
        json=conflict_payload,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE_CONFLICT"

    assert user_b.get("/api/v1/channels").json()["total"] == 0
    cross_user_patch = user_b.patch(
        f"/api/v1/channels/{channel_id}",
        headers={"X-CSRF-Token": csrf_b},
        json={"name": "越权修改"},
    )
    assert cross_user_patch.status_code == 404

    sender_payload = {
        "platform_id": platform_id,
        "external_id": "teacher-1",
        "display_name": "张老师",
        "source_type": "TEACHER",
        "credibility": 0.95,
    }
    created_sender = user_a.post(
        "/api/v1/senders",
        headers={"X-CSRF-Token": csrf_a},
        json=sender_payload,
    )
    assert created_sender.status_code == 201
    sender_id = created_sender.json()["id"]
    assert user_b.get("/api/v1/senders").json()["total"] == 0
    assert (
        user_b.patch(
            f"/api/v1/senders/{sender_id}",
            headers={"X-CSRF-Token": csrf_b},
            json={"display_name": "越权修改"},
        ).status_code
        == 404
    )

    disabled = admin.patch(
        f"/api/v1/admin/platforms/{platform_id}",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"status": "DISABLED"},
    )
    assert disabled.status_code == 200
    assert user_a.get("/api/v1/platforms").json()["items"] == []
    rejected = user_b.post(
        "/api/v1/channels",
        headers={"X-CSRF-Token": csrf_b},
        json={**channel_payload, "external_id": "group-other"},
    )
    assert rejected.status_code == 404
