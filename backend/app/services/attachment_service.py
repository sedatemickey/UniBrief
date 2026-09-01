"""Controlled local attachment download, retry, and authorization helpers."""

from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import AttachmentStatus
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models import MessageAttachment
from app.repositories import attachment_repository


def _validate_remote_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise AppError(400, "ATTACHMENT_UNSAFE_URL", "附件 URL 不安全")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AppError(502, "NETWORK_ERROR", "附件域名解析失败", retryable=True) from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise AppError(400, "ATTACHMENT_UNSAFE_URL", "附件 URL 指向受限网络地址")


def _safe_file_name(file_name: str) -> str:
    name = Path(file_name).name.strip().replace("\x00", "")
    if not name or name in {".", ".."}:
        return "attachment.bin"
    return name[:200]


def _owned_attachment(db: Session, attachment_id: int, user_id: int) -> MessageAttachment:
    attachment = attachment_repository.get_owned(db, attachment_id=attachment_id, user_id=user_id)
    if attachment is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    return attachment


def get_owned_attachment(db: Session, attachment_id: int, user_id: int) -> MessageAttachment:
    """Load attachment metadata only through its current user's Message."""

    return _owned_attachment(db, attachment_id, user_id)


def schedule_retry(db: Session, attachment_id: int, user_id: int) -> MessageAttachment:
    """Return a failed/pending attachment to PENDING for a background retry."""

    attachment = _owned_attachment(db, attachment_id, user_id)
    if attachment.download_status not in {
        AttachmentStatus.FAILED.value,
        AttachmentStatus.PENDING.value,
    }:
        raise AppError(409, "INVALID_STATE", "当前附件状态不允许重试")
    max_attempts = get_settings().attachment_max_retries + 1
    if attachment.download_attempts >= max_attempts:
        raise AppError(409, "INVALID_STATE", "附件已达到最大下载尝试次数")
    attachment.download_status = AttachmentStatus.PENDING.value
    attachment.last_error = None
    db.commit()
    db.refresh(attachment)
    return attachment


def attachment_file_path(
    db: Session, attachment_id: int, user_id: int
) -> tuple[MessageAttachment, Path]:
    """Resolve an authorized downloaded file and detect DB/disk divergence."""

    attachment = _owned_attachment(db, attachment_id, user_id)
    if attachment.download_status != AttachmentStatus.DOWNLOADED.value:
        raise AppError(409, "INVALID_STATE", "附件尚未下载完成")
    if not attachment.storage_key:
        attachment.download_status = AttachmentStatus.FAILED.value
        attachment.last_error = "ATTACHMENT_FILE_MISSING"
        db.commit()
        raise AppError(404, "ATTACHMENT_FILE_MISSING", "附件文件不存在")
    root = get_settings().attachment_storage_dir.resolve()
    path = (root / attachment.storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        attachment.download_status = AttachmentStatus.FAILED.value
        attachment.storage_key = None
        attachment.last_error = "ATTACHMENT_FILE_MISSING"
        db.commit()
        raise AppError(404, "ATTACHMENT_FILE_MISSING", "附件文件不存在")
    return attachment, path


def recover_pending_downloads() -> list[int]:
    """Recover committed PENDING and stale DOWNLOADING rows after process startup."""

    settings = get_settings()
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        seconds=settings.attachment_downloading_stale_seconds
    )
    with SessionLocal() as db:
        rows = attachment_repository.recoverable(
            db,
            pending_status=AttachmentStatus.PENDING.value,
            downloading_status=AttachmentStatus.DOWNLOADING.value,
            stale_before=cutoff,
            max_attempts=settings.attachment_max_retries + 1,
        )
        for row in rows:
            row.download_status = AttachmentStatus.PENDING.value
            row.last_error = "RECOVERED_AFTER_RESTART"
        db.commit()
        return [row.id for row in rows]


def mark_missing_downloaded_files() -> int:
    """Mark DOWNLOADED rows failed when their controlled local file disappeared."""

    root = get_settings().attachment_storage_dir.resolve()
    changed = 0
    with SessionLocal() as db:
        rows = attachment_repository.by_status(db, AttachmentStatus.DOWNLOADED.value)
        for row in rows:
            path = (root / row.storage_key).resolve() if row.storage_key else None
            if path is None or not path.is_relative_to(root) or not path.is_file():
                row.download_status = AttachmentStatus.FAILED.value
                row.storage_key = None
                row.last_error = "ATTACHMENT_FILE_MISSING"
                changed += 1
        db.commit()
    return changed


def _mark_failed(attachment_id: int, code: str) -> None:
    with SessionLocal() as db:
        attachment = attachment_repository.get(db, attachment_id)
        if attachment is None:
            return
        attachment.download_status = AttachmentStatus.FAILED.value
        attachment.last_error = code[:512]
        db.commit()


def download_attachment(attachment_id: int) -> None:
    """Download one attachment after Message metadata committed."""

    settings = get_settings()
    temp_path: Path | None = None
    try:
        with SessionLocal() as db:
            attachment = attachment_repository.get(db, attachment_id)
            if attachment is None or attachment.download_status not in {
                AttachmentStatus.PENDING.value,
                AttachmentStatus.FAILED.value,
            }:
                return
            if attachment.download_attempts >= settings.attachment_max_retries + 1:
                attachment.download_status = AttachmentStatus.FAILED.value
                attachment.last_error = "ATTACHMENT_MAX_RETRIES"
                db.commit()
                return
            message = attachment_repository.get_message(db, attachment.message_id)
            if message is None:
                return
            attachment.download_status = AttachmentStatus.DOWNLOADING.value
            attachment.download_attempts += 1
            attachment.last_error = None
            db.commit()
            file_url = attachment.file_url
            file_name = attachment.file_name
            user_id = message.user_id
            message_id = message.id

        current_url = file_url
        final_response: httpx.Response | None = None
        with httpx.Client(
            timeout=settings.attachment_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "UniBrief/0.1 attachment-downloader"},
        ) as client:
            for redirect_count in range(settings.attachment_max_redirects + 1):
                _validate_remote_url(current_url)
                request = client.build_request("GET", current_url)
                streamed = client.send(request, stream=True)
                if streamed.status_code in {301, 302, 303, 307, 308}:
                    location = streamed.headers.get("location")
                    streamed.close()
                    if not location or redirect_count >= settings.attachment_max_redirects:
                        raise AppError(502, "NETWORK_ERROR", "附件重定向无效", retryable=True)
                    current_url = urljoin(current_url, location)
                    continue
                streamed.raise_for_status()
                final_response = streamed
                break
            if final_response is None:
                raise AppError(502, "NETWORK_ERROR", "附件重定向次数过多", retryable=True)

            declared_size = final_response.headers.get("content-length")
            if declared_size and int(declared_size) > settings.attachment_max_bytes:
                final_response.close()
                raise AppError(413, "ATTACHMENT_TOO_LARGE", "附件超过大小限制")

            root = settings.attachment_storage_dir.resolve()
            relative = (
                Path(str(user_id))
                / str(message_id)
                / f"{attachment_id}-{_safe_file_name(file_name)}"
            )
            final_path = (root / relative).resolve()
            if not final_path.is_relative_to(root):
                final_response.close()
                raise AppError(400, "ATTACHMENT_UNSAFE_URL", "附件存储路径不安全")
            final_path.parent.mkdir(parents=True, exist_ok=True)
            digest = sha256()
            size = 0
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, dir=final_path.parent, prefix=".download-"
            ) as temporary:
                temp_path = Path(temporary.name)
                for chunk in final_response.iter_bytes():
                    size += len(chunk)
                    if size > settings.attachment_max_bytes:
                        raise AppError(413, "ATTACHMENT_TOO_LARGE", "附件超过大小限制")
                    digest.update(chunk)
                    temporary.write(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            final_response.close()
            os.replace(temp_path, final_path)
            temp_path = None

        with SessionLocal() as db:
            attachment = attachment_repository.get(db, attachment_id)
            if attachment is None:
                final_path.unlink(missing_ok=True)
                return
            attachment.storage_key = relative.as_posix()
            attachment.file_size = size
            attachment.sha256 = digest.hexdigest()
            attachment.download_status = AttachmentStatus.DOWNLOADED.value
            attachment.downloaded_at = datetime.now(UTC).replace(tzinfo=None)
            attachment.last_error = None
            db.commit()
    except AppError as exc:
        _mark_failed(attachment_id, exc.code)
    except httpx.TimeoutException:
        _mark_failed(attachment_id, "TIMEOUT")
    except httpx.HTTPError:
        _mark_failed(attachment_id, "NETWORK_ERROR")
    except (OSError, ValueError):
        _mark_failed(attachment_id, "PERSISTENCE_ERROR")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
