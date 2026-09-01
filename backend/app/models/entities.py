"""The complete 16-table SQLAlchemy model for the multi-user MVP."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, MEDIUMTEXT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    AttachmentStatus,
    DictionaryStatus,
    EventStatus,
    InformationStatus,
    MessageStatus,
    ReminderStatus,
    UserStatus,
)
from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserStatus.ACTIVE.value,
        server_default=UserStatus.ACTIVE.value,
    )
    session_version: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, default=1, server_default="1"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SystemSetting(Base):
    __tablename__ = "system_setting"
    setting_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_text: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    description: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Platform(Base):
    __tablename__ = "platform"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DictionaryStatus.ACTIVE.value,
        server_default=DictionaryStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Channel(Base):
    __tablename__ = "channel"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "platform_id",
            "external_id",
            name="uq_channel_user_platform_external",
        ),
        UniqueConstraint("user_id", "id", name="uq_channel_user_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    platform_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("platform.id", ondelete="RESTRICT"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Sender(Base):
    __tablename__ = "sender"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "platform_id",
            "external_id",
            name="uq_sender_user_platform_external",
        ),
        UniqueConstraint("user_id", "id", name="uq_sender_user_id"),
        CheckConstraint("credibility BETWEEN 0 AND 1", name="credibility_range"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    platform_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("platform.id", ondelete="RESTRICT"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    credibility: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, default=Decimal("0.500"), server_default="0.500"
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "channel_id",
            "external_id",
            name="uq_message_user_channel_external",
        ),
        UniqueConstraint("user_id", "id", name="uq_message_user_id"),
        ForeignKeyConstraint(
            ["user_id", "channel_id"], ["channel.user_id", "channel.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["user_id", "sender_id"], ["sender.user_id", "sender.id"], ondelete="RESTRICT"
        ),
        Index("ix_message_user_channel_sent", "user_id", "channel_id", "sent_at"),
        Index("ix_message_user_sender_sent", "user_id", "sender_id", "sent_at"),
        Index("ix_message_user_status_ingested", "user_id", "process_status", "ingested_at"),
        Index("ix_message_status_processing", "process_status", "processing_started_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sender_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    external_id: Mapped[str] = mapped_column(String(191), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    process_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MessageStatus.PENDING.value,
        server_default=MessageStatus.PENDING.value,
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime)


class MessageAttachment(TimestampMixin, Base):
    __tablename__ = "message_attachment"
    __table_args__ = (UniqueConstraint("message_id", "external_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("message.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(191), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    sha256: Mapped[str | None] = mapped_column(String(64))
    download_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AttachmentStatus.PENDING.value,
        server_default=AttachmentStatus.PENDING.value,
    )
    download_attempts: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, default=0, server_default="0"
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(512))
    extracted_text: Mapped[str | None] = mapped_column(Text)


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = (Index("ix_ai_analysis_message_analyzed", "message_id", "analyzed_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("message.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    useful: Mapped[bool | None] = mapped_column(Boolean)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(512))
    latency_ms: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    raw_result: Mapped[dict | None] = mapped_column(JSON)
    raw_response_text: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class InformationItem(TimestampMixin, Base):
    __tablename__ = "information_item"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint("importance BETWEEN 1 AND 5", name="importance_range"),
        Index(
            "ix_information_user_status_importance_created",
            "user_id",
            "status",
            "importance",
            "created_at",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    importance: Mapped[int] = mapped_column(TINYINT, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=InformationStatus.ACTIVE.value,
        server_default=InformationStatus.ACTIVE.value,
    )
    version: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, default=1, server_default="1"
    )


class MessageInformation(Base):
    __tablename__ = "message_information"
    __table_args__ = (
        PrimaryKeyConstraint("message_id", "information_id"),
        ForeignKeyConstraint(
            ["user_id", "message_id"], ["message.user_id", "message.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["user_id", "information_id"],
            ["information_item.user_id", "information_item.id"],
            ondelete="CASCADE",
        ),
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    information_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Category(Base):
    __tablename__ = "category"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DictionaryStatus.ACTIVE.value,
        server_default=DictionaryStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class InformationCategory(Base):
    __tablename__ = "information_category"
    information_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("information_item.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("category.id", ondelete="RESTRICT"), primary_key=True
    )


class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
        UniqueConstraint("user_id", "id", name="uq_tag_user_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class InformationTag(Base):
    __tablename__ = "information_tag"
    __table_args__ = (
        PrimaryKeyConstraint("information_id", "tag_id"),
        ForeignKeyConstraint(
            ["user_id", "information_id"],
            ["information_item.user_id", "information_item.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["user_id", "tag_id"], ["tag.user_id", "tag.id"], ondelete="RESTRICT"),
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    information_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tag_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Event(TimestampMixin, Base):
    __tablename__ = "event"
    __table_args__ = (
        CheckConstraint("start_at IS NOT NULL OR deadline IS NOT NULL", name="time_present"),
        CheckConstraint(
            "start_at IS NULL OR deadline IS NULL OR deadline >= start_at", name="time_order"
        ),
        Index("ix_event_deadline", "deadline"),
        Index("ix_event_status_deadline", "event_status", "deadline"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    information_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("information_item.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    event_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EventStatus.UPCOMING.value,
        server_default=EventStatus.UPCOMING.value,
    )


class EventReminder(TimestampMixin, Base):
    __tablename__ = "event_reminder"
    __table_args__ = (Index("ix_reminder_status_remind_at", "reminder_status", "remind_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("event.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reminder_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ReminderStatus.PENDING.value,
        server_default=ReminderStatus.PENDING.value,
    )
    is_custom_time: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
