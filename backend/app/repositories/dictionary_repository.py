"""Persistence queries for global Platform and Category dictionaries."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Platform


def list_platforms(
    db: Session, *, status: str | None, offset: int, limit: int
) -> tuple[list[Platform], int]:
    """Execute the scoped persistence operation."""

    filters = [Platform.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(Platform).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Platform)
            .where(*filters)
            .order_by(Platform.name.asc(), Platform.id.asc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def list_active_platforms(db: Session) -> list[Platform]:
    """Execute the scoped persistence operation."""

    return list(
        db.scalars(
            select(Platform).where(Platform.status == "ACTIVE").order_by(Platform.name.asc())
        )
    )


def get_platform(db: Session, platform_id: int) -> Platform | None:
    """Execute the scoped persistence operation."""

    return db.get(Platform, platform_id)


def get_active_platform(db: Session, platform_id: int) -> Platform | None:
    """Execute the scoped persistence operation."""

    return db.scalar(
        select(Platform).where(Platform.id == platform_id, Platform.status == "ACTIVE")
    )


def get_active_platform_by_identity(
    db: Session, *, name: str, platform_type: str
) -> Platform | None:
    """Execute the scoped persistence operation."""

    return db.scalar(
        select(Platform).where(
            Platform.name == name,
            Platform.type == platform_type,
            Platform.status == "ACTIVE",
        )
    )


def add_platform(db: Session, platform: Platform) -> None:
    """Execute the scoped persistence operation."""

    db.add(platform)


def list_categories(
    db: Session, *, status: str | None, offset: int, limit: int
) -> tuple[list[Category], int]:
    """Execute the scoped persistence operation."""

    filters = [Category.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(Category).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Category)
            .where(*filters)
            .order_by(Category.name.asc(), Category.id.asc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total


def list_active_categories(db: Session) -> list[Category]:
    """Execute the scoped persistence operation."""

    return list(
        db.scalars(
            select(Category).where(Category.status == "ACTIVE").order_by(Category.name.asc())
        )
    )


def get_category(db: Session, category_id: int) -> Category | None:
    """Execute the scoped persistence operation."""

    return db.get(Category, category_id)


def add_category(db: Session, category: Category) -> None:
    """Execute the scoped persistence operation."""

    db.add(category)
