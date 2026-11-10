"""Validate and append the 60-message synthetic AI demo dataset."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
DEFAULT_DATA_PATH = REPOSITORY_ROOT / "sample_data" / "pending_ai_messages_60.json"
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from app.core.enums import MessageStatus, UserStatus
from app.core.errors import AppError
from app.db.session import SessionLocal, check_database, engine
from app.models import Message, User
from app.schemas.messages import MessageImportItem, MessageImportRequest
from app.services.ingestion_service import import_messages
from sqlalchemy import select

ALLOWED_DATABASES = {"unibrief", "unibrief_test"}


def parse_args() -> argparse.Namespace:
    """Parse the append-only dataset import options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="目标普通用户名；默认读取数据文件中的 target_username")
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="待导入的合成消息 JSON 文件",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="只校验数据文件，不连接或写入数据库",
    )
    return parser.parse_args()


def load_and_validate(path: Path) -> tuple[dict[str, Any], list[MessageImportRequest], list[str]]:
    """Load the dataset and strictly validate all ingestion requests."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    batches = payload.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("batches 必须是非空数组")

    requests: list[MessageImportRequest] = []
    external_ids: list[str] = []
    for index, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict):
            raise TypeError(f"第 {index} 个 batch 不是对象")
        request = MessageImportRequest.model_validate(
            {
                "platform": batch.get("platform"),
                "channel": batch.get("channel"),
                "messages": batch.get("messages"),
            }
        )
        validated_messages = [MessageImportItem.model_validate(item) for item in request.messages]
        expected_count = batch.get("expected_count")
        if expected_count != len(validated_messages):
            raise ValueError(
                f"第 {index} 个 batch 的 expected_count={expected_count}，"
                f"实际为 {len(validated_messages)}"
            )
        requests.append(request)
        external_ids.extend(item.external_id for item in validated_messages)

    expected_total = payload.get("expected_total")
    if expected_total != len(external_ids):
        raise ValueError(f"expected_total={expected_total}，实际为 {len(external_ids)}")
    if len(set(external_ids)) != len(external_ids):
        raise ValueError("数据文件中存在重复 external_id")
    if expected_total != 60:
        raise ValueError("本演示数据集必须固定包含 60 条消息")
    if payload.get("expected_useless") != 8:
        raise ValueError("本演示数据集必须固定包含 8 条无用闲聊")
    return payload, requests, external_ids


def import_dataset(
    *, username: str, requests: list[MessageImportRequest], external_ids: list[str]
) -> dict[str, Any]:
    """Append the dataset through the production ingestion service and verify it."""

    status = check_database(engine)
    if status.database_name not in ALLOWED_DATABASES:
        raise RuntimeError(f"拒绝写入非开发/测试数据库：{status.database_name}")

    inserted = duplicates = failed = 0
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(
                User.username == username,
                User.status == UserStatus.ACTIVE.value,
            )
        )
        if user is None:
            raise RuntimeError(f"未找到 ACTIVE 普通用户：{username}")

        for request in requests:
            try:
                response, attachment_ids = import_messages(
                    db,
                    user_id=user.id,
                    request=request,
                )
            except AppError as exc:
                raise RuntimeError(f"导入批次失败：{exc.code} {exc.message}") from exc
            if attachment_ids:
                raise RuntimeError("此数据集不应创建附件下载任务")
            inserted += response.inserted
            duplicates += response.duplicates
            failed += response.failed

        rows = list(
            db.scalars(
                select(Message)
                .where(
                    Message.user_id == user.id,
                    Message.external_id.in_(external_ids),
                )
                .order_by(Message.id)
            )
        )

    found_ids = {row.external_id for row in rows}
    missing = sorted(set(external_ids) - found_ids)
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.process_status] = status_counts.get(row.process_status, 0) + 1

    if failed:
        raise RuntimeError(f"存在 {failed} 条导入失败")
    if missing or len(rows) != 60:
        raise RuntimeError(f"数据库验证失败：找到 {len(rows)} 条，缺失 {len(missing)} 条")
    if status_counts != {MessageStatus.PENDING.value: 60}:
        raise RuntimeError(
            "数据已导入，但部分消息不再是 PENDING；可能已被手工或后台 AI 分析："
            f"{status_counts}"
        )

    return {
        "database": status.database_name,
        "username": username,
        "inserted": inserted,
        "duplicates": duplicates,
        "failed": failed,
        "pending": status_counts.get(MessageStatus.PENDING.value, 0),
        "message_ids": [row.id for row in rows],
    }


def main() -> None:
    """Validate the file, optionally append it, and print a safe summary."""

    args = parse_args()
    data_path = args.data.resolve()
    payload, requests, external_ids = load_and_validate(data_path)
    username = args.username or payload.get("target_username")
    if not isinstance(username, str) or not username:
        raise SystemExit("必须通过 --username 或 target_username 指定目标用户")

    if args.check_only:
        print(
            json.dumps(
                {
                    "dataset_id": payload.get("dataset_id"),
                    "batches": len(requests),
                    "messages": len(external_ids),
                    "expected_useless": payload.get("expected_useless"),
                    "status": "VALID",
                },
                ensure_ascii=False,
            )
        )
        return

    result = import_dataset(username=username, requests=requests, external_ids=external_ids)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()


