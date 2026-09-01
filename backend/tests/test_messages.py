"""Integration tests for idempotent ingestion, evidence preservation, and isolation."""

from fastapi.testclient import TestClient

from app.core.security import ADMIN_CSRF_COOKIE, USER_CSRF_COOKIE, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.services.setting_service import set_setting


def _provision() -> tuple[TestClient, str, int]:
    with SessionLocal() as db:
        set_setting(db, "admin_password_hash", hash_password("AdminPass123"))
        db.commit()
    admin = TestClient(app)
    assert (
        admin.post("/api/v1/admin/auth/login", json={"password": "AdminPass123"}).status_code == 200
    )
    admin_csrf = admin.cookies.get(ADMIN_CSRF_COOKIE)
    platform = admin.post(
        "/api/v1/admin/platforms",
        headers={"X-Admin-CSRF-Token": admin_csrf},
        json={"name": "QQ", "type": "IM"},
    )
    platform_id = platform.json()["id"]
    for username in ("user_a", "user_b"):
        created = admin.post(
            "/api/v1/admin/users",
            headers={"X-Admin-CSRF-Token": admin_csrf},
            json={
                "username": username,
                "display_name": username,
                "password": "ExamplePass123",
            },
        )
        assert created.status_code == 201
    return admin, admin_csrf, platform_id


def _login(username: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "ExamplePass123"},
    )
    assert response.status_code == 200
    csrf = client.cookies.get(USER_CSRF_COOKIE)
    assert csrf
    return client, csrf


def _payload(*, content: str = "课程设计报告 9 月 20 日前提交") -> dict:
    return {
        "platform": {"name": "QQ", "type": "IM"},
        "channel": {
            "external_id": "group-123",
            "name": "数据库课程群",
            "channel_type": "GROUP",
        },
        "messages": [
            {
                "external_id": "msg-1001",
                "sender": {
                    "external_id": "teacher-1",
                    "display_name": "张老师",
                    "source_type": "TEACHER",
                },
                "content": content,
                "sent_at": "2026-09-01T09:30:00+08:00",
                "attachments": [],
            }
        ],
    }


def test_message_import_duplicate_conflict_partial_validation_and_isolation() -> None:
    _provision()
    user_a, csrf_a = _login("user_a")
    user_b, csrf_b = _login("user_b")

    inserted = user_a.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_a},
        json=_payload(),
    )
    assert inserted.status_code == 200
    assert inserted.json()["inserted"] == 1
    message_id = inserted.json()["results"][0]["message_id"]

    duplicate = user_a.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_a},
        json=_payload(),
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicates"] == 1
    assert user_a.get("/api/v1/messages").json()["total"] == 1

    conflict = user_a.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_a},
        json=_payload(content="被冲突导入伪造的新原文"),
    )
    assert conflict.status_code == 400
    assert conflict.json()["error"]["code"] == "IMPORT_PARTIAL_FAILURE"
    assert (
        conflict.json()["error"]["details"]["results"][0]["error"]["code"] == "DUPLICATE_CONFLICT"
    )
    detail = user_a.get(f"/api/v1/messages/{message_id}")
    assert detail.status_code == 200
    assert detail.json()["content"] == "课程设计报告 9 月 20 日前提交"
    assert detail.json()["sent_at"] == "2026-09-01T01:30:00Z"

    partial_payload = _payload()
    partial_payload["messages"] = [
        {
            **partial_payload["messages"][0],
            "external_id": "msg-1002",
            "content": "第二条有效通知",
        },
        {
            "external_id": "msg-invalid",
            "sender": {"external_id": "teacher-1", "display_name": "张老师"},
            "content": "缺少时区",
            "sent_at": "2026-09-01T10:00:00",
        },
    ]
    partial = user_a.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_a},
        json=partial_payload,
    )
    assert partial.status_code == 200
    assert partial.json()["inserted"] == 1
    assert partial.json()["failed"] == 1
    assert partial.json()["results"][1]["error"]["code"] == "VALIDATION_ERROR"

    assert user_b.get("/api/v1/messages").json()["total"] == 0
    assert user_b.get(f"/api/v1/messages/{message_id}").status_code == 404
    same_external_other_user = user_b.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_b},
        json=_payload(),
    )
    assert same_external_other_user.status_code == 200
    assert same_external_other_user.json()["inserted"] == 1

    ranged = user_a.get(
        "/api/v1/messages",
        params={
            "sent_from": "2026-09-01T01:30:00Z",
            "sent_to": "2026-09-01T01:31:00Z",
        },
    )
    assert ranged.status_code == 200
    assert ranged.json()["total"] == 2
    boundary_excluded = user_a.get(
        "/api/v1/messages",
        params={
            "sent_from": "2026-09-01T01:29:00Z",
            "sent_to": "2026-09-01T01:30:00Z",
        },
    )
    assert boundary_excluded.json()["total"] == 0


def test_attachment_failure_does_not_rollback_message_and_is_authorized() -> None:
    _provision()
    user_a, csrf_a = _login("user_a")
    user_b, _csrf_b = _login("user_b")
    payload = _payload()
    payload["messages"][0]["external_id"] = "msg-with-file"
    payload["messages"][0]["attachments"] = [
        {
            "external_id": "file-1",
            "file_name": "要求.pdf",
            "file_type": "application/pdf",
            "file_url": "http://127.0.0.1/private/requirement.pdf?token=secret",
        }
    ]

    imported = user_a.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_a},
        json=payload,
    )
    assert imported.status_code == 200
    assert imported.json()["inserted"] == 1
    assert imported.json()["attachment_metadata_created"] == 1
    message_id = imported.json()["results"][0]["message_id"]

    detail = user_a.get(f"/api/v1/messages/{message_id}")
    assert detail.status_code == 200
    attachment = detail.json()["attachments"][0]
    assert attachment["download_status"] == "FAILED"
    assert attachment["last_error"] == "ATTACHMENT_UNSAFE_URL"
    duplicate = user_a.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_a},
        json=payload,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicates"] == 1
    assert duplicate.json()["attachment_metadata_created"] == 0
    assert len(user_a.get(f"/api/v1/messages/{message_id}").json()["attachments"]) == 1
    assert "file_url" not in attachment
    assert "storage_key" not in attachment
    attachment_id = attachment["id"]
    retry = user_a.post(
        f"/api/v1/attachments/{attachment_id}/retry-download",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert retry.status_code == 202
    assert retry.json() == {
        "id": attachment_id,
        "download_status": "PENDING",
        "scheduled": True,
    }
    after_retry = user_a.get(f"/api/v1/attachments/{attachment_id}")
    assert after_retry.json()["download_status"] == "FAILED"
    assert after_retry.json()["download_attempts"] == 2
    assert user_b.get(f"/api/v1/attachments/{attachment_id}").status_code == 404
    assert user_b.get(f"/api/v1/attachments/{attachment_id}/download").status_code == 404


def test_csv_adapter_uses_unified_idempotent_import_contract() -> None:
    _provision()
    user_a, csrf_a = _login("user_a")
    header = ",".join(
        [
            "platform_name",
            "platform_type",
            "channel_external_id",
            "channel_name",
            "channel_type",
            "message_external_id",
            "sender_external_id",
            "sender_display_name",
            "sender_source_type",
            "content",
            "sent_at",
        ]
    )
    rows = [
        "QQ,IM,group-csv,CSV课程群,GROUP,csv-1,teacher-csv,李老师,TEACHER,第一条CSV通知,2026-09-01T09:00:00+08:00",
        "QQ,IM,group-csv,CSV课程群,GROUP,csv-2,teacher-csv,李老师,TEACHER,第二条CSV通知,2026-09-01T10:00:00+08:00",
    ]
    csv_content = "\n".join([header, *rows, ""])
    imported = user_a.post(
        "/api/v1/messages/import-csv",
        headers={"X-CSRF-Token": csrf_a},
        files={"file": ("messages.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["inserted"] == 2
    duplicate = user_a.post(
        "/api/v1/messages/import-csv",
        headers={"X-CSRF-Token": csrf_a},
        files={"file": ("messages.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicates"] == 2

    missing_columns = user_a.post(
        "/api/v1/messages/import-csv",
        headers={"X-CSRF-Token": csrf_a},
        files={"file": ("bad.csv", b"platform_name,content\nQQ,test\n", "text/csv")},
    )
    assert missing_columns.status_code == 400
    assert missing_columns.json()["error"]["code"] == "VALIDATION_ERROR"


def test_successful_attachment_is_local_authorized_and_missing_file_is_detected(
    tmp_path, monkeypatch
) -> None:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.models import MessageAttachment
    from app.services import attachment_service

    _provision()
    user_a, csrf_a = _login("user_a")
    user_b, _csrf_b = _login("user_b")
    payload = _payload()
    payload["messages"][0]["external_id"] = "msg-download-success"
    payload["messages"][0]["attachments"] = [
        {
            "external_id": "file-success",
            "file_name": "safe.txt",
            "file_type": "text/plain",
            "file_url": "http://127.0.0.1/initially-blocked",
        }
    ]
    imported = user_a.post(
        "/api/v1/messages/import",
        headers={"X-CSRF-Token": csrf_a},
        json=payload,
    )
    assert imported.status_code == 200

    with SessionLocal() as db:
        attachment = db.scalar(
            select(MessageAttachment).where(MessageAttachment.external_id == "file-success")
        )
        attachment_id = attachment.id
        attachment.file_url = "https://example.edu/safe.txt"
        attachment.download_status = "PENDING"
        attachment.download_attempts = 0
        attachment.last_error = None
        db.commit()

    body = b"controlled attachment content"

    class FakeResponse:
        status_code = 200
        headers = {"content-length": str(len(body))}

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self):
            yield body[:10]
            yield body[10:]

        def close(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def build_request(self, method: str, url: str):
            return (method, url)

        def send(self, request, stream: bool = False):
            return FakeResponse()

    test_settings = get_settings().model_copy(
        update={"attachment_storage_dir": tmp_path / "attachments"}
    )
    monkeypatch.setattr(attachment_service, "get_settings", lambda: test_settings)
    monkeypatch.setattr(attachment_service, "_validate_remote_url", lambda _url: None)
    monkeypatch.setattr(attachment_service.httpx, "Client", FakeClient)

    attachment_service.download_attachment(attachment_id)
    metadata = user_a.get(f"/api/v1/attachments/{attachment_id}")
    assert metadata.status_code == 200
    assert metadata.json()["download_status"] == "DOWNLOADED"
    assert metadata.json()["file_size"] == len(body)
    assert len(metadata.json()["sha256"]) == 64
    downloaded = user_a.get(f"/api/v1/attachments/{attachment_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == body
    assert user_b.get(f"/api/v1/attachments/{attachment_id}").status_code == 404

    with SessionLocal() as db:
        attachment = db.get(MessageAttachment, attachment_id)
        local_path = test_settings.attachment_storage_dir / attachment.storage_key
    local_path.unlink()
    missing = user_a.get(f"/api/v1/attachments/{attachment_id}/download")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ATTACHMENT_FILE_MISSING"
