"""User persistence queries shared by auth and administrator services."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import User


def get_by_id(db: Session, user_id: int) -> User | None:
    """Load one normal user by primary key."""

    return db.get(User, user_id)


def get_by_username(db: Session, username: str) -> User | None:
    """Load one normal user by unique username."""

    return db.scalar(select(User).where(User.username == username))


def add(db: Session, user: User) -> None:
    """Stage a new normal user in the current transaction."""

    db.add(user)


def list_page(
    db: Session,
    *,
    keyword: str | None,
    status: str | None,
    offset: int,
    limit: int,
    sort: str,
) -> tuple[list[User], int]:
    """Return a filtered page and total count without private-data joins."""

    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(or_(User.username.like(pattern), User.display_name.like(pattern)))
    if status:
        filters.append(User.status == status)
    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    order = User.username.asc() if sort == "username_asc" else User.created_at.desc()
    items = list(
        db.scalars(
            select(User).where(*filters).order_by(order, User.id.asc()).offset(offset).limit(limit)
        )
    )
    return items, total
