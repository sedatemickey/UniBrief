"""Persistence access for the whitelisted system_setting table."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemSetting


def get(db: Session, key: str) -> SystemSetting | None:
    """Load one setting row by its registered key."""

    return db.scalar(select(SystemSetting).where(SystemSetting.setting_key == key))


def add(db: Session, setting: SystemSetting) -> None:
    """Stage a registered setting row in the current transaction."""

    db.add(setting)
