"""Global pytest safety guard and isolated MySQL reset fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPOSITORY_ROOT / ".env"


def _read_env_value(key: str) -> str | None:
    if not ENV_FILE.exists():
        return os.environ.get(key)
    prefix = f"{key}="
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return os.environ.get(key)


test_database_url = os.environ.get("TEST_DATABASE_URL") or _read_env_value("TEST_DATABASE_URL")
if not test_database_url:
    raise RuntimeError("pytest requires TEST_DATABASE_URL; refusing to use DATABASE_URL")

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = test_database_url

from app.db.session import engine  # noqa: E402

CORE_TABLES = [
    "event_reminder",
    "event",
    "information_tag",
    "information_category",
    "message_information",
    "ai_analysis",
    "message_attachment",
    "message",
    "tag",
    "information_item",
    "sender",
    "channel",
    "platform",
    "category",
    "user",
    "system_setting",
]
SEED_CATEGORIES = [
    ("课程", "课程安排与教学信息"),
    ("作业", "作业、报告与提交要求"),
    ("考试", "考试、测验与复习安排"),
    ("活动", "校园活动与社团通知"),
    ("通知", "行政及综合通知"),
    ("其他", "暂未归入其他分类的信息"),
]


def _reset_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in CORE_TABLES:
            connection.execute(text(f"TRUNCATE TABLE `{table}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        connection.execute(
            text(
                """
                INSERT INTO system_setting
                    (setting_key, value_text, value_type, is_sensitive, description)
                VALUES
                    ('registration_enabled', 'false', 'BOOLEAN', 0, '是否允许普通用户自助注册'),
                    ('admin_session_version', '1', 'INTEGER', 1, '管理员会话失效版本')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO category (name, description, status)
                VALUES (:name, :description, 'ACTIVE')
                """
            ),
            [{"name": name, "description": description} for name, description in SEED_CATEGORIES],
        )
        connection.commit()


@pytest.fixture(autouse=True)
def reset_database() -> None:
    """Reset the dedicated test schema and restore deterministic migration seeds."""

    _reset_database()
    yield
    _reset_database()
