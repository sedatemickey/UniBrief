"""Information, Tag, Event, and Reminder routes for the ordinary user UI."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DbSession, current_user, user_csrf
from app.core.enums import EventStatus, InformationStatus, ReminderStatus
from app.models import Tag, User
from app.schemas.information import (
    EventDetail,
    EventPage,
    EventPatch,
    InformationDetail,
    InformationPage,
    InformationPatch,
    LinkMessageRequest,
    MessageInformationResponse,
    PopularTag,
    ReminderListItem,
    ReminderPage,
    ReminderPatch,
    TagCreate,
    TagPage,
    TagPatch,
    TagResponse,
)
from app.services import event_service, information_service

router = APIRouter(tags=["information"])


@router.get("/information", response_model=InformationPage)
def information_list(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    category_ids: Annotated[list[int] | None, Query()] = None,
    tag_ids: Annotated[list[int] | None, Query()] = None,
    importance_min: Annotated[int | None, Query(ge=1, le=5)] = None,
    importance_max: Annotated[int | None, Query(ge=1, le=5)] = None,
    status: InformationStatus | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    event_from: datetime | None = None,
    event_to: datetime | None = None,
    keyword: str | None = None,
    sort: Literal[
        "created_at_desc", "updated_at_desc", "importance_desc", "deadline_asc"
    ] = "created_at_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InformationPage:
    """List Information with URL-persistable combined filters."""

    return information_service.list_information(
        db,
        user_id=user.id,
        category_ids=category_ids or [],
        tag_ids=tag_ids or [],
        importance_min=importance_min,
        importance_max=importance_max,
        status=status.value if status else None,
        created_from=created_from,
        created_to=created_to,
        event_from=event_from,
        event_to=event_to,
        keyword=keyword,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/information/{information_id}", response_model=InformationDetail)
def information_detail(
    information_id: int,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
) -> InformationDetail:
    """Return Information details and provenance."""

    return information_service.get_information(
        db, user_id=user.id, information_id=information_id
    )


@router.patch("/information/{information_id}", response_model=InformationDetail)
def information_patch(
    information_id: int,
    payload: InformationPatch,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> InformationDetail:
    """Optimistically edit Information and explicit Category/Tag collections."""

    return information_service.patch_information(
        db,
        user_id=user.id,
        information_id=information_id,
        payload=payload,
    )


@router.post(
    "/information/{information_id}/link-message/{message_id}",
    response_model=MessageInformationResponse,
)
def information_link_message(
    information_id: int,
    message_id: int,
    payload: LinkMessageRequest,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> MessageInformationResponse:
    """Idempotently add an owned Message provenance edge."""

    return information_service.link_message(
        db,
        user_id=user.id,
        information_id=information_id,
        message_id=message_id,
        relation_type=payload.relation_type.value,
    )


@router.get("/tags", response_model=TagPage)
def tags_list(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    keyword: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TagPage:
    """List private Tags."""

    return information_service.list_tags(
        db, user_id=user.id, keyword=keyword, page=page, page_size=page_size
    )


@router.get("/tags/popular", response_model=list[PopularTag])
def tags_popular(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[PopularTag]:
    """Return popular private Tags."""

    return information_service.popular_tags(
        db,
        user_id=user.id,
        limit=limit,
        created_from=created_from,
        created_to=created_to,
    )


@router.post("/tags", response_model=TagResponse, status_code=201)
def tag_create(
    payload: TagCreate,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> Tag:
    """Create one private Tag."""

    return information_service.create_tag(db, user_id=user.id, name=payload.name)


@router.patch("/tags/{tag_id}", response_model=TagResponse)
def tag_patch(
    tag_id: int,
    payload: TagPatch,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> Tag:
    """Rename one private Tag."""

    return information_service.patch_tag(
        db, user_id=user.id, tag_id=tag_id, name=payload.name
    )


@router.get("/events", response_model=EventPage)
def events_list(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    status: EventStatus | None = None,
    sort: Literal["start_at_asc", "deadline_asc", "updated_at_desc"] = "start_at_asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 100,
) -> EventPage:
    """List Events for calendar and agenda using one range contract."""

    return event_service.list_events(
        db,
        user_id=user.id,
        range_start=range_start,
        range_end=range_end,
        status=status.value if status else None,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/events/{event_id}", response_model=EventDetail)
def event_detail(
    event_id: int,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
) -> EventDetail:
    """Return one owned Event and Reminder."""

    return event_service.get_event(db, user_id=user.id, event_id=event_id)


@router.patch("/events/{event_id}", response_model=EventDetail)
def event_patch(
    event_id: int,
    payload: EventPatch,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> EventDetail:
    """Edit Event time/status with Information version protection."""

    return event_service.patch_event(
        db, user_id=user.id, event_id=event_id, payload=payload
    )


@router.get("/reminders", response_model=ReminderPage)
def reminders_list(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    status: ReminderStatus | None = None,
    remind_from: datetime | None = None,
    remind_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReminderPage:
    """List current-user reminders."""

    return event_service.list_reminders(
        db,
        user_id=user.id,
        status=status.value if status else None,
        remind_from=remind_from,
        remind_to=remind_to,
        page=page,
        page_size=page_size,
    )


@router.patch("/reminders/{reminder_id}", response_model=ReminderListItem)
def reminder_patch(
    reminder_id: int,
    payload: ReminderPatch,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> ReminderListItem:
    """Customize or enable/disable one reminder."""

    return event_service.patch_reminder(
        db, user_id=user.id, reminder_id=reminder_id, payload=payload
    )


@router.post("/reminders/{reminder_id}/read", response_model=ReminderListItem)
def reminder_read(
    reminder_id: int,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> ReminderListItem:
    """Mark one DUE reminder READ idempotently."""

    return event_service.read_reminder(db, user_id=user.id, reminder_id=reminder_id)

