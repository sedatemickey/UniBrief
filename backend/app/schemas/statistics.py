"""Response schemas for current-user database statistics."""

from datetime import date

from pydantic import BaseModel, Field


class StatisticsOverview(BaseModel):
    message_total: int
    information_active_total: int
    event_upcoming_total: int
    reminder_due_total: int


class ChannelStatistic(BaseModel):
    channel_id: int
    channel_name: str
    platform_id: int
    platform_name: str
    message_count: int
    effective_message_count: int
    effectiveness_rate: float = Field(ge=0, le=1)


class CategoryStatistic(BaseModel):
    category_id: int
    category_name: str
    information_count: int


class TagStatistic(BaseModel):
    tag_id: int
    tag_name: str
    usage_count: int


class UpcomingEventDay(BaseModel):
    date: date
    count: int


class UpcomingEventStatistics(BaseModel):
    days: int
    total: int
    by_date: list[UpcomingEventDay]
