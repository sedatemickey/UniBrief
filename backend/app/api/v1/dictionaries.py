"""Global Platform and Category routes for admin and normal users."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import DbSession, admin_csrf, current_admin, current_user
from app.models import Category, Platform, User
from app.schemas.resources import (
    CategoryCreate,
    CategoryList,
    CategoryPage,
    CategoryPatch,
    CategoryResponse,
    PlatformCreate,
    PlatformList,
    PlatformPage,
    PlatformPatch,
    PlatformResponse,
)
from app.services import dictionary_service

admin_router = APIRouter(prefix="/admin", tags=["admin-dictionaries"])
public_router = APIRouter(tags=["dictionaries"])


@admin_router.get("/platforms", response_model=PlatformPage)
def admin_platforms(
    db: DbSession,
    _admin: Annotated[bool, Depends(current_admin)],
    platform_status: Annotated[Literal["ACTIVE", "DISABLED"] | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PlatformPage:
    """Handle the documented API operation."""

    items, total, total_pages = dictionary_service.list_platforms(
        db, status=platform_status, page=page, page_size=page_size
    )
    return PlatformPage(
        items=[PlatformResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@admin_router.post(
    "/platforms", response_model=PlatformResponse, status_code=status.HTTP_201_CREATED
)
def create_platform(
    payload: PlatformCreate,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> Platform:
    """Handle the documented API operation."""

    return dictionary_service.create_platform(db, payload)


@admin_router.patch("/platforms/{platform_id}", response_model=PlatformResponse)
def update_platform(
    platform_id: int,
    payload: PlatformPatch,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> Platform:
    """Handle the documented API operation."""

    return dictionary_service.update_platform(db, platform_id, payload)


@admin_router.get("/categories", response_model=CategoryPage)
def admin_categories(
    db: DbSession,
    _admin: Annotated[bool, Depends(current_admin)],
    category_status: Annotated[Literal["ACTIVE", "DISABLED"] | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CategoryPage:
    """Handle the documented API operation."""

    items, total, total_pages = dictionary_service.list_categories(
        db, status=category_status, page=page, page_size=page_size
    )
    return CategoryPage(
        items=[CategoryResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@admin_router.post(
    "/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
def create_category(
    payload: CategoryCreate,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> Category:
    """Handle the documented API operation."""

    return dictionary_service.create_category(db, payload)


@admin_router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryPatch,
    db: DbSession,
    _csrf: Annotated[None, Depends(admin_csrf)],
) -> Category:
    """Handle the documented API operation."""

    return dictionary_service.update_category(db, category_id, payload)


@public_router.get("/platforms", response_model=PlatformList)
def active_platforms(db: DbSession, _user: Annotated[User, Depends(current_user)]) -> PlatformList:
    """Handle the documented API operation."""

    return PlatformList(
        items=[
            PlatformResponse.model_validate(item)
            for item in dictionary_service.list_active_platforms(db)
        ]
    )


@public_router.get("/categories", response_model=CategoryList)
def active_categories(db: DbSession, _user: Annotated[User, Depends(current_user)]) -> CategoryList:
    """Handle the documented API operation."""

    return CategoryList(
        items=[
            CategoryResponse.model_validate(item)
            for item in dictionary_service.list_active_categories(db)
        ]
    )
