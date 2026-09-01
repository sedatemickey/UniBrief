"""Global Platform and Category dictionary services."""

from math import ceil

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Platform
from app.repositories import dictionary_repository
from app.schemas.resources import CategoryCreate, CategoryPatch, PlatformCreate, PlatformPatch


def _commit_unique(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "VALIDATION_ERROR", conflict_message) from exc


def list_platforms(
    db: Session, *, status: str | None, page: int, page_size: int
) -> tuple[list[Platform], int, int]:
    """List global platforms with optional status filtering."""

    items, total = dictionary_repository.list_platforms(
        db, status=status, offset=(page - 1) * page_size, limit=page_size
    )
    return items, total, ceil(total / page_size) if total else 0


def list_active_platforms(db: Session) -> list[Platform]:
    """Return only active platforms to normal users."""

    return dictionary_repository.list_active_platforms(db)


def create_platform(db: Session, payload: PlatformCreate) -> Platform:
    """Create an administrator-managed global platform."""

    platform = Platform(**payload.model_dump())
    dictionary_repository.add_platform(db, platform)
    _commit_unique(db, "平台名称已存在")
    db.refresh(platform)
    return platform


def update_platform(db: Session, platform_id: int, payload: PlatformPatch) -> Platform:
    """Update a platform without deleting referenced history."""

    platform = dictionary_repository.get_platform(db, platform_id)
    if platform is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(platform, key, value)
    _commit_unique(db, "平台名称已存在")
    db.refresh(platform)
    return platform


def list_categories(
    db: Session, *, status: str | None, page: int, page_size: int
) -> tuple[list[Category], int, int]:
    """List global categories with optional status filtering."""

    items, total = dictionary_repository.list_categories(
        db, status=status, offset=(page - 1) * page_size, limit=page_size
    )
    return items, total, ceil(total / page_size) if total else 0


def list_active_categories(db: Session) -> list[Category]:
    """Return only active categories to normal users."""

    return dictionary_repository.list_active_categories(db)


def create_category(db: Session, payload: CategoryCreate) -> Category:
    """Create an administrator-managed global category."""

    category = Category(**payload.model_dump())
    dictionary_repository.add_category(db, category)
    _commit_unique(db, "分类名称已存在")
    db.refresh(category)
    return category


def update_category(db: Session, category_id: int, payload: CategoryPatch) -> Category:
    """Update a category while preserving referenced history."""

    category = dictionary_repository.get_category(db, category_id)
    if category is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    for key in payload.model_fields_set:
        setattr(category, key, getattr(payload, key))
    _commit_unique(db, "分类名称已存在")
    db.refresh(category)
    return category
