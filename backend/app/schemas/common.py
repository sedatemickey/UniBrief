"""Small schema serialization helpers."""

from datetime import UTC, datetime


def utc_iso(value: datetime | None) -> str | None:
    """Serialize a MySQL UTC-naive DATETIME as an RFC 3339 UTC string."""

    if value is None:
        return None
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")
