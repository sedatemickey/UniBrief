"""Authenticated statistics routes backed by MySQL queries and advanced objects."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DbSession, current_user
from app.models import User
from app.schemas.statistics import (
    CategoryStatistic,
    ChannelStatistic,
    StatisticsOverview,
    TagStatistic,
    UpcomingEventStatistics,
)
from app.services import statistics_service

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/overview", response_model=StatisticsOverview)
def overview(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    start: datetime | None = None,
    end: datetime | None = None,
) -> StatisticsOverview:
    """Return dashboard totals for the current user."""

    return statistics_service.overview(
        db,
        user_id=user.id,
        start=start,
        end=end,
    )


@router.get("/channels", response_model=list[ChannelStatistic])
def channels(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    start: datetime,
    end: datetime,
    platform_id: int | None = None,
) -> list[ChannelStatistic]:
    """Return channel volume and effectiveness from the stored procedure."""

    return statistics_service.channels(
        db,
        user_id=user.id,
        start=start,
        end=end,
        platform_id=platform_id,
    )


@router.get("/categories", response_model=list[CategoryStatistic])
def categories(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    start: datetime,
    end: datetime,
    include_archived: bool = False,
) -> list[CategoryStatistic]:
    """Return Category distribution for one half-open time window."""

    return statistics_service.categories(
        db,
        user_id=user.id,
        start=start,
        end=end,
        include_archived=include_archived,
    )


@router.get("/tags", response_model=list[TagStatistic])
def tags(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    start: datetime,
    end: datetime,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[TagStatistic]:
    """Return private Tag popularity for one half-open time window."""

    return statistics_service.tags(
        db,
        user_id=user.id,
        start=start,
        end=end,
        include_archived=include_archived,
        limit=limit,
    )


@router.get("/upcoming-events", response_model=UpcomingEventStatistics)
def upcoming_events(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> UpcomingEventStatistics:
    """Aggregate upcoming Events from Shanghai today for a bounded horizon."""

    return statistics_service.upcoming_events(db, user_id=user.id, days=days)
