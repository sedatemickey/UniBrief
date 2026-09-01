"""Private Channel and Sender management routes."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import DbSession, current_user, user_csrf
from app.models import Channel, Sender, User
from app.schemas.resources import (
    ChannelCreate,
    ChannelPage,
    ChannelPatch,
    ChannelResponse,
    SenderCreate,
    SenderPage,
    SenderPatch,
    SenderResponse,
)
from app.services import source_service

router = APIRouter(tags=["sources"])


@router.get("/channels", response_model=ChannelPage)
def channels(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    platform_id: int | None = None,
    keyword: str | None = None,
    channel_type: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ChannelPage:
    """Handle the documented API operation."""

    items, total, total_pages = source_service.list_channels(
        db,
        user_id=user.id,
        platform_id=platform_id,
        keyword=keyword,
        channel_type=channel_type,
        page=page,
        page_size=page_size,
    )
    return ChannelPage(
        items=[ChannelResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post("/channels", response_model=ChannelResponse)
def create_channel(
    payload: ChannelCreate,
    response: Response,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> Channel:
    """Handle the documented API operation."""

    channel, created = source_service.create_channel(db, user.id, payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return channel


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
def update_channel(
    channel_id: int,
    payload: ChannelPatch,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> Channel:
    """Handle the documented API operation."""

    return source_service.update_channel(db, user.id, channel_id, payload)


@router.get("/senders", response_model=SenderPage)
def senders(
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    platform_id: int | None = None,
    keyword: str | None = None,
    source_type: str | None = None,
    credibility_min: Annotated[Decimal | None, Query(ge=0, le=1)] = None,
    credibility_max: Annotated[Decimal | None, Query(ge=0, le=1)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SenderPage:
    """Handle the documented API operation."""

    items, total, total_pages = source_service.list_senders(
        db,
        user_id=user.id,
        platform_id=platform_id,
        keyword=keyword,
        source_type=source_type,
        credibility_min=credibility_min,
        credibility_max=credibility_max,
        page=page,
        page_size=page_size,
    )
    return SenderPage(
        items=[SenderResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post("/senders", response_model=SenderResponse)
def create_sender(
    payload: SenderCreate,
    response: Response,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> Sender:
    """Handle the documented API operation."""

    sender, created = source_service.create_sender(db, user.id, payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return sender


@router.patch("/senders/{sender_id}", response_model=SenderResponse)
def update_sender(
    sender_id: int,
    payload: SenderPatch,
    db: DbSession,
    user: Annotated[User, Depends(current_user)],
    _csrf: Annotated[None, Depends(user_csrf)],
) -> Sender:
    """Handle the documented API operation."""

    return source_service.update_sender(db, user.id, sender_id, payload)
