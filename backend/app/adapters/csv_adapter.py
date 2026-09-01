"""UTF-8 CSV adapter for the unified JSON ingestion contract."""

from __future__ import annotations

import csv
import io
from collections import defaultdict

from app.core.errors import AppError
from app.schemas.messages import MessageImportRequest

CSV_COLUMNS = [
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
CSV_MAX_BYTES = 10 * 1024 * 1024


def parse_csv(content: bytes) -> list[MessageImportRequest]:
    """Group CSV rows by platform/channel and emit unified import requests."""

    if len(content) > CSV_MAX_BYTES:
        raise AppError(413, "VALIDATION_ERROR", "CSV 文件超过 10 MiB 限制")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError(400, "VALIDATION_ERROR", "CSV 必须使用 UTF-8 编码") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None:
            raise AppError(400, "VALIDATION_ERROR", "CSV 缺少表头")
        missing = [column for column in CSV_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise AppError(
                400,
                "VALIDATION_ERROR",
                "CSV 缺少必需列",
                details={"missing_columns": missing},
            )
        groups: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
        for row in reader:
            if not any((value or "").strip() for value in row.values()):
                continue
            key = (
                row["platform_name"],
                row["platform_type"],
                row["channel_external_id"],
                row["channel_name"],
                row["channel_type"],
            )
            groups[key].append(
                {
                    "external_id": row["message_external_id"],
                    "sender": {
                        "external_id": row["sender_external_id"],
                        "display_name": row["sender_display_name"],
                        "source_type": row["sender_source_type"] or "UNKNOWN",
                    },
                    "content": row["content"],
                    "sent_at": row["sent_at"],
                    "attachments": [],
                }
            )
    except csv.Error as exc:
        raise AppError(400, "VALIDATION_ERROR", "CSV 格式错误") from exc
    if not groups:
        raise AppError(400, "VALIDATION_ERROR", "CSV 不包含消息数据")
    return [
        MessageImportRequest(
            platform={"name": key[0], "type": key[1]},
            channel={
                "external_id": key[2],
                "name": key[3],
                "channel_type": key[4],
            },
            messages=messages,
        )
        for key, messages in groups.items()
    ]
