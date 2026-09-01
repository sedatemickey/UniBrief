"""Whitelisted access to the system_setting table."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.enums import SettingValueType
from app.core.errors import AppError
from app.models import SystemSetting
from app.repositories import setting_repository


@dataclass(frozen=True)
class SettingDefinition:
    value_type: SettingValueType
    sensitive: bool
    description: str


SETTING_DEFINITIONS = {
    "registration_enabled": SettingDefinition(
        SettingValueType.BOOLEAN, False, "是否允许普通用户自助注册"
    ),
    "admin_password_hash": SettingDefinition(
        SettingValueType.SECRET, True, "管理员 Argon2id 密码哈希"
    ),
    "admin_session_version": SettingDefinition(
        SettingValueType.INTEGER, True, "管理员会话失效版本"
    ),
}


def _definition(key: str) -> SettingDefinition:
    try:
        return SETTING_DEFINITIONS[key]
    except KeyError as exc:
        raise AppError(400, "VALIDATION_ERROR", "未知的系统设置键") from exc


def get_raw_setting(db: Session, key: str) -> SystemSetting | None:
    """Read a registered setting without exposing it through an API response."""

    _definition(key)
    return setting_repository.get(db, key)


def get_bool_setting(db: Session, key: str) -> bool:
    """Read and strictly parse a BOOLEAN setting."""

    definition = _definition(key)
    if definition.value_type is not SettingValueType.BOOLEAN:
        raise RuntimeError(f"Setting {key} is not BOOLEAN")
    row = get_raw_setting(db, key)
    if row is None or row.value_text not in {"true", "false"}:
        raise RuntimeError(f"Invalid BOOLEAN setting: {key}")
    return row.value_text == "true"


def get_int_setting(db: Session, key: str) -> int:
    """Read and strictly parse an INTEGER setting."""

    definition = _definition(key)
    if definition.value_type is not SettingValueType.INTEGER:
        raise RuntimeError(f"Setting {key} is not INTEGER")
    row = get_raw_setting(db, key)
    if row is None:
        raise RuntimeError(f"Missing INTEGER setting: {key}")
    try:
        return int(row.value_text)
    except ValueError as exc:
        raise RuntimeError(f"Invalid INTEGER setting: {key}") from exc


def set_setting(db: Session, key: str, value: bool | int | str) -> SystemSetting:
    """Write only a registered setting using its declared type."""

    definition = _definition(key)
    if definition.value_type is SettingValueType.BOOLEAN:
        if not isinstance(value, bool):
            raise AppError(400, "VALIDATION_ERROR", "设置值类型错误")
        value_text = "true" if value else "false"
    elif definition.value_type is SettingValueType.INTEGER:
        if not isinstance(value, int) or isinstance(value, bool):
            raise AppError(400, "VALIDATION_ERROR", "设置值类型错误")
        value_text = str(value)
    else:
        if not isinstance(value, str) or not value:
            raise AppError(400, "VALIDATION_ERROR", "设置值类型错误")
        value_text = value

    row = get_raw_setting(db, key)
    if row is None:
        row = SystemSetting(
            setting_key=key,
            value_text=value_text,
            value_type=definition.value_type.value,
            is_sensitive=definition.sensitive,
            description=definition.description,
        )
        setting_repository.add(db, row)
    else:
        row.value_text = value_text
        row.value_type = definition.value_type.value
        row.is_sensitive = definition.sensitive
        row.description = definition.description
    return row
