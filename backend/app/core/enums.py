"""Central string enums persisted by the relational model."""

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class DictionaryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class MessageStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    IGNORED = "IGNORED"


class AttachmentStatus(StrEnum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class AnalysisStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class InformationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    UPDATED = "UPDATED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


class RelationType(StrEnum):
    CREATE = "CREATE"
    SUPPORT = "SUPPORT"
    UPDATE = "UPDATE"
    CORRECTION = "CORRECTION"


class EventStatus(StrEnum):
    UPCOMING = "UPCOMING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ReminderStatus(StrEnum):
    PENDING = "PENDING"
    DUE = "DUE"
    READ = "READ"
    DISABLED = "DISABLED"


class SettingValueType(StrEnum):
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    SECRET = "SECRET"
