"""Validation and presentation logic for current-user statistics."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.repositories import statistics_repository
from app.schemas.statistics import (
    CategoryStatistic,
    ChannelStatistic,
    StatisticsOverview,
    TagStatistic,
    UpcomingEventDay,
    UpcomingEventStatistics,
)
from app.services.ingestion_service import utc_naive

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def overview(
    db: Session,
    *,
    user_id: int,
    start: datetime | None,
    end: datetime | None,
) -> StatisticsOverview:
    """Return the four dashboard totals with optional paired time bounds."""

    normalized = _optional_range(start, end)
    return StatisticsOverview.model_validate(
        statistics_repository.overview(
            db,
            user_id=user_id,
            start=normalized[0],
            end=normalized[1],
        )
    )


def channels(
    db: Session,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
    platform_id: int | None,
) -> list[ChannelStatistic]:
    """Return stored-procedure channel effectiveness rows."""

    start_utc, end_utc = _required_range(start, end)
    rows = statistics_repository.channel_statistics(
        db,
        user_id=user_id,
        start=start_utc,
        end=end_utc,
    )
    return [
        ChannelStatistic(
            channel_id=row["channel_id"],
            channel_name=row["channel_name"],
            platform_id=row["platform_id"],
            platform_name=row["platform_name"],
            message_count=row["message_count"],
            effective_message_count=row["effective_message_count"],
            effectiveness_rate=float(row["effectiveness_rate"]),
        )
        for row in rows
        if platform_id is None or row["platform_id"] == platform_id
    ]


def categories(
    db: Session,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
    include_archived: bool,
) -> list[CategoryStatistic]:
    """Return Category distribution in one half-open window."""

    start_utc, end_utc = _required_range(start, end)
    return [
        CategoryStatistic.model_validate(row)
        for row in statistics_repository.category_statistics(
            db,
            user_id=user_id,
            start=start_utc,
            end=end_utc,
            include_archived=include_archived,
        )
    ]


def tags(
    db: Session,
    *,
    user_id: int,
    start: datetime,
    end: datetime,
    include_archived: bool,
    limit: int,
) -> list[TagStatistic]:
    """Return current-user Tag popularity in one half-open window."""

    start_utc, end_utc = _required_range(start, end)
    return [
        TagStatistic.model_validate(row)
        for row in statistics_repository.tag_statistics(
            db,
            user_id=user_id,
            start=start_utc,
            end=end_utc,
            include_archived=include_archived,
            limit=limit,
        )
    ]


def upcoming_events(
    db: Session,
    *,
    user_id: int,
    days: int,
    now: datetime | None = None,
) -> UpcomingEventStatistics:
    """Aggregate upcoming Events by Shanghai local date."""

    current = now.astimezone(_SHANGHAI) if now else datetime.now(_SHANGHAI)
    local_start = datetime.combine(current.date(), time.min, tzinfo=_SHANGHAI)
    local_end = local_start + timedelta(days=days)
    start_utc = local_start.astimezone(UTC).replace(tzinfo=None)
    end_utc = local_end.astimezone(UTC).replace(tzinfo=None)
    counts: Counter[date] = Counter()
    for start_at, deadline in statistics_repository.upcoming_event_times(
        db,
        user_id=user_id,
        start=start_utc,
        end=end_utc,
    ):
        anchor = start_at or deadline
        if anchor is None:
            continue
        local_date = anchor.replace(tzinfo=UTC).astimezone(_SHANGHAI).date()
        counts[local_date] += 1
    by_date = [
        UpcomingEventDay(date=day, count=counts.get(day, 0))
        for day in (current.date() + timedelta(days=index) for index in range(days))
    ]
    return UpcomingEventStatistics(days=days, total=sum(counts.values()), by_date=by_date)


def _optional_range(
    start: datetime | None, end: datetime | None
) -> tuple[datetime | None, datetime | None]:
    if (start is None) != (end is None):
        raise AppError(400, "VALIDATION_ERROR", "start 和 end 必须同时提供")
    if start is None or end is None:
        return None, None
    return _required_range(start, end)


def _required_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start_utc = utc_naive(start)
    end_utc = utc_naive(end)
    if start_utc >= end_utc:
        raise AppError(400, "VALIDATION_ERROR", "start 必须早于 end")
    return start_utc, end_utc
