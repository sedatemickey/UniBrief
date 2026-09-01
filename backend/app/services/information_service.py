"""Business rules for Information, provenance, and private Tag resources."""

from __future__ import annotations

from datetime import datetime
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import DictionaryStatus
from app.core.errors import AppError
from app.models import Category, MessageInformation, Tag
from app.repositories import analysis_repository, information_repository
from app.schemas.information import (
    InformationDetail,
    InformationEventSummary,
    InformationPage,
    InformationPatch,
    InformationSource,
    InformationSummary,
    MessageInformationResponse,
    NamedResource,
    PopularTag,
    ReminderSummary,
    TagPage,
    TagResponse,
)
from app.services.ingestion_service import utc_naive


def list_information(
    db: Session,
    *,
    user_id: int,
    category_ids: list[int],
    tag_ids: list[int],
    importance_min: int | None,
    importance_max: int | None,
    status: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    event_from: datetime | None,
    event_to: datetime | None,
    keyword: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> InformationPage:
    """List owned Information with combined filters and stable pagination."""

    created_range = _optional_range(created_from, created_to, "created_from", "created_to")
    event_range = _optional_range(event_from, event_to, "event_from", "event_to")
    if importance_min and importance_max and importance_min > importance_max:
        raise AppError(400, "VALIDATION_ERROR", "importance_min 不能大于 importance_max")
    ids, total = information_repository.list_information_ids(
        db,
        user_id=user_id,
        category_ids=category_ids,
        tag_ids=tag_ids,
        importance_min=importance_min,
        importance_max=importance_max,
        status=status,
        created_from=created_range[0],
        created_to=created_range[1],
        event_from=event_range[0],
        event_to=event_range[1],
        keyword=keyword,
        sort=sort,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return InformationPage(
        items=_summaries(db, user_id, ids),
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


def get_information(db: Session, *, user_id: int, information_id: int) -> InformationDetail:
    """Return one Information with Event, Reminder, and provenance Messages."""

    information = information_repository.get_owned_information(db, user_id, information_id)
    if information is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    summary = _summaries(db, user_id, [information_id])[0]
    event = information_repository.events_for_information(db, [information_id]).get(information_id)
    reminder = information_repository.reminder_for_event(db, event.id) if event else None
    sources = information_repository.information_sources(
        db, user_id=user_id, information_id=information_id
    )
    return InformationDetail(
        **summary.model_dump(),
        reminder=(
            ReminderSummary.model_validate(reminder, from_attributes=True)
            if reminder
            else None
        ),
        sources=[
            InformationSource(
                message_id=message.id,
                relation_type=relation.relation_type,
                content=message.content,
                sent_at=message.sent_at,
                channel_name=channel.name,
                sender_display_name=sender.display_name,
            )
            for relation, message, channel, sender in sources
        ],
    )


def patch_information(
    db: Session,
    *,
    user_id: int,
    information_id: int,
    payload: InformationPatch,
) -> InformationDetail:
    """Optimistically patch scalar fields and explicit relation collections."""

    current = information_repository.get_owned_information(db, user_id, information_id)
    if current is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    values = {
        field: getattr(payload, field).value
        if field == "status"
        else getattr(payload, field)
        for field in ("title", "summary", "importance", "status")
        if field in payload.model_fields_set
    }
    if not information_repository.optimistic_patch_information(
        db,
        user_id=user_id,
        information_id=information_id,
        expected_version=payload.expected_version,
        values=values,
    ):
        db.rollback()
        latest = information_repository.get_owned_information(db, user_id, information_id)
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "信息已被其他操作更新",
            retryable=True,
            details={"current_version": latest.version if latest else None},
        )
    if "category_ids" in payload.model_fields_set:
        category_ids = payload.category_ids or []
        if category_ids:
            active_count = db.scalar(
                select(Category.id)
                .where(
                    Category.id.in_(category_ids),
                    Category.status == DictionaryStatus.ACTIVE.value,
                )
                .with_only_columns(func.count(Category.id))
            )
            if active_count != len(category_ids):
                db.rollback()
                raise AppError(400, "VALIDATION_ERROR", "分类不存在或已停用")
        names = list(db.scalars(select(Category.name).where(Category.id.in_(category_ids))))
        analysis_repository.set_information_categories(
            db,
            information_id=information_id,
            names=names,
            replace=True,
        )
    if "tag_names" in payload.model_fields_set:
        analysis_repository.set_information_tags(
            db,
            user_id=user_id,
            information_id=information_id,
            names=payload.tag_names or [],
            replace=True,
        )
    db.commit()
    return get_information(db, user_id=user_id, information_id=information_id)


def link_message(
    db: Session,
    *,
    user_id: int,
    information_id: int,
    message_id: int,
    relation_type: str,
) -> MessageInformationResponse:
    """Idempotently link one owned evidence Message."""

    if information_repository.get_owned_information(db, user_id, information_id) is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    if information_repository.get_owned_message(db, user_id, message_id) is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    relation = information_repository.get_message_relation(db, message_id, information_id)
    if relation is None:
        relation = MessageInformation(
            user_id=user_id,
            message_id=message_id,
            information_id=information_id,
            relation_type=relation_type,
        )
        db.add(relation)
        db.commit()
    return MessageInformationResponse(
        message_id=message_id,
        information_id=information_id,
        relation_type=relation.relation_type,
    )


def list_tags(
    db: Session,
    *,
    user_id: int,
    keyword: str | None,
    page: int,
    page_size: int,
) -> TagPage:
    """List private Tags."""

    items, total = information_repository.list_tags(
        db,
        user_id=user_id,
        keyword=keyword,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return TagPage(
        items=[TagResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


def create_tag(db: Session, *, user_id: int, name: str) -> Tag:
    """Create one user-private unique Tag."""

    existing = information_repository.get_tag_by_name(db, user_id, name)
    if existing:
        raise AppError(409, "TAG_CONFLICT", "标签名称已存在")
    tag = Tag(user_id=user_id, name=name)
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "TAG_CONFLICT", "标签名称已存在") from exc
    return tag


def patch_tag(db: Session, *, user_id: int, tag_id: int, name: str) -> Tag:
    """Rename one private Tag while preserving uniqueness."""

    tag = information_repository.get_tag(db, user_id, tag_id)
    if tag is None:
        raise AppError(404, "NOT_FOUND", "资源不存在")
    conflict = information_repository.get_tag_by_name(db, user_id, name)
    if conflict and conflict.id != tag_id:
        raise AppError(409, "TAG_CONFLICT", "标签名称已存在")
    tag.name = name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "TAG_CONFLICT", "标签名称已存在") from exc
    return tag


def popular_tags(
    db: Session,
    *,
    user_id: int,
    limit: int,
    created_from: datetime | None,
    created_to: datetime | None,
) -> list[PopularTag]:
    """Return popular private Tags with an optional creation window."""

    window = _optional_range(created_from, created_to, "created_from", "created_to")
    return [
        PopularTag(id=tag_id, name=name, usage_count=count)
        for tag_id, name, count in information_repository.popular_tags(
            db,
            user_id=user_id,
            created_from=window[0],
            created_to=window[1],
            limit=limit,
        )
    ]


def _summaries(db: Session, user_id: int, ids: list[int]) -> list[InformationSummary]:
    items = information_repository.list_information(db, user_id, ids)
    categories = information_repository.categories_for_information(db, ids)
    tags = information_repository.tags_for_information(db, user_id, ids)
    events = information_repository.events_for_information(db, ids)
    return [
        InformationSummary(
            id=item.id,
            title=item.title,
            summary=item.summary,
            source_type=item.source_type,
            importance=item.importance,
            confidence=float(item.confidence),
            status=item.status,
            version=item.version,
            created_at=item.created_at,
            updated_at=item.updated_at,
            categories=[
                NamedResource(id=value.id, name=value.name)
                for value in categories[item.id]
            ],
            tags=[NamedResource(id=value.id, name=value.name) for value in tags[item.id]],
            event=(
                InformationEventSummary.model_validate(events[item.id], from_attributes=True)
                if item.id in events
                else None
            ),
        )
        for item in items
    ]


def _optional_range(
    start: datetime | None,
    end: datetime | None,
    start_name: str,
    end_name: str,
) -> tuple[datetime | None, datetime | None]:
    if (start is None) != (end is None):
        raise AppError(400, "VALIDATION_ERROR", f"{start_name} 和 {end_name} 必须同时提供")
    if start is None or end is None:
        return None, None
    start_utc, end_utc = utc_naive(start), utc_naive(end)
    if start_utc >= end_utc:
        raise AppError(400, "VALIDATION_ERROR", "时间范围起点必须早于终点")
    return start_utc, end_utc

