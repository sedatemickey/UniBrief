"""SQLAlchemy engine, sessions, and MySQL environment validation."""

from collections.abc import Generator
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@dataclass(frozen=True)
class DatabaseStatus:
    """Non-sensitive database properties used by readiness checks."""

    version: str
    database_name: str
    character_set: str
    collation: str
    session_time_zone: str

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-serializable status mapping."""

        return asdict(self)


def _set_utc_time_zone(dbapi_connection: Any, _connection_record: Any) -> None:
    """Force each MySQL connection to interpret DATETIME values as UTC."""

    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a pooled SQLAlchemy engine for the configured MySQL database."""

    engine = create_engine(
        database_url or get_settings().database_url,
        pool_pre_ping=True,
        future=True,
    )
    event.listen(engine, "connect", _set_utc_time_zone)
    return engine


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    """Yield one request-scoped database session and always close it."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database(target_engine: Engine) -> DatabaseStatus:
    """Verify MySQL version, utf8mb4 database defaults, and UTC session time zone."""

    query = text(
        """
        SELECT
            VERSION() AS version,
            DATABASE() AS database_name,
            @@character_set_database AS character_set,
            @@collation_database AS collation,
            @@session.time_zone AS session_time_zone
        """
    )
    with target_engine.connect() as connection:
        row = connection.execute(query).mappings().one()

    status = DatabaseStatus(**dict(row))
    if not status.version.startswith("8."):
        raise RuntimeError("UniBrief requires MySQL 8.x.")
    if status.character_set.lower() != "utf8mb4":
        raise RuntimeError("The configured database must use utf8mb4.")
    if status.session_time_zone != "+00:00":
        raise RuntimeError("The MySQL session time zone must be +00:00.")
    return status
