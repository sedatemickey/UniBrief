"""Manual single and batch AI analysis with short database transactions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai import ProviderError, ProviderResult
from app.ai.prompts import build_analysis_messages
from app.core.enums import (
    AnalysisStatus,
    EventStatus,
    InformationStatus,
    MessageStatus,
    ReminderStatus,
)
from app.core.errors import AppError
from app.models import AIAnalysis, Event, EventReminder, InformationItem, Message
from app.repositories import analysis_repository
from app.schemas.ai import (
    AIInformationOutput,
    AIMessageOutput,
    AnalyzeBatchItemResponse,
    AnalyzeBatchResponse,
    AnalyzeResponse,
    BatchItemError,
    CandidateInformation,
)
from app.services import ai_service

_compare_locks: dict[int, asyncio.Lock] = {}
_compare_locks_guard = asyncio.Lock()


@dataclass
class AnalysisRunError(Exception):
    """Internal failure that retains one batch item's persisted audit metadata."""

    message_id: int
    status: str
    code: str
    message: str
    retryable: bool
    http_status: int
    analysis_id: int | None = None


class ConcurrentInformationUpdate(Exception):
    """Signal that an optimistic InformationItem write lost its race."""


async def analyze_single(
    db: Session,
    *,
    user_id: int,
    message_id: int,
    requested_model: str | None,
    mode: str,
) -> AnalyzeResponse:
    """Analyze one owned Message and surface its classified error mapping."""

    model = ai_service.resolve_model(requested_model)
    try:
        return await _analyze_one(
            db,
            user_id=user_id,
            message_id=message_id,
            model=model,
            mode=mode,
        )
    except AnalysisRunError as exc:
        details = {
            "message_id": exc.message_id,
            "process_status": exc.status,
            "analysis_id": exc.analysis_id,
        }
        raise AppError(
            exc.http_status,
            exc.code,
            exc.message,
            retryable=exc.retryable,
            details=details,
        ) from exc


async def analyze_batch(
    db: Session,
    *,
    user_id: int,
    message_ids: list[int],
    requested_model: str | None,
    mode: str,
) -> AnalyzeBatchResponse:
    """Process each owned Message in an independent short transaction."""

    model = ai_service.resolve_model(requested_model)
    if analysis_repository.count_owned_messages(db, user_id, message_ids) != len(message_ids):
        raise AppError(404, "NOT_FOUND", "消息不存在")
    db.rollback()
    results: list[AnalyzeBatchItemResponse] = []
    for message_id in message_ids:
        try:
            item = await _analyze_one(
                db,
                user_id=user_id,
                message_id=message_id,
                model=model,
                mode=mode,
            )
            results.append(
                AnalyzeBatchItemResponse(
                    message_id=message_id,
                    status=item.process_status,
                    analysis_id=item.analysis_id,
                    business_applied=item.business_applied,
                    information_ids=item.information_ids,
                )
            )
        except AnalysisRunError as exc:
            db.rollback()
            results.append(
                AnalyzeBatchItemResponse(
                    message_id=message_id,
                    status=exc.status,
                    analysis_id=exc.analysis_id,
                    business_applied=False,
                    error=BatchItemError(
                        code=exc.code,
                        retryable=exc.retryable,
                        message=exc.message,
                    ),
                )
            )
    return AnalyzeBatchResponse(mode=mode, results=results)


async def _analyze_one(
    db: Session,
    *,
    user_id: int,
    message_id: int,
    model: str,
    mode: str,
) -> AnalyzeResponse:
    if mode == "compare":
        lock = await _compare_lock(message_id)
        async with lock:
            return await _run_compare(db, user_id, message_id, model)
    return await _run_retry(db, user_id, message_id, model)


async def _run_compare(
    db: Session, user_id: int, message_id: int, model: str
) -> AnalyzeResponse:
    message = analysis_repository.get_owned_message(db, user_id, message_id)
    if message is None:
        raise _run_error(message_id, MessageStatus.FAILED.value, "NOT_FOUND", "消息不存在", 404)
    if message.process_status not in {MessageStatus.PROCESSED.value, MessageStatus.IGNORED.value}:
        raise _run_error(
            message_id,
            message.process_status,
            "INVALID_STATE",
            "compare 仅允许已处理或已忽略的消息",
            409,
        )
    original_status = message.process_status
    snapshot = _prompt_snapshot(db, user_id, message_id)
    provider_messages = build_analysis_messages(*snapshot[:2], snapshot[2])
    db.rollback()
    try:
        result = await ai_service.provider().analyze(
            model=model,
            messages=provider_messages,
        )
        _validate_candidate_targets(result, snapshot[2])
    except ProviderError as exc:
        analysis_id = _record_failure(
            db,
            message_id=message_id,
            model=model,
            error=exc,
            change_message_state=False,
        )
        raise AnalysisRunError(
            message_id,
            original_status,
            exc.code,
            exc.message,
            exc.retryable,
            exc.http_status,
            analysis_id,
        ) from exc
    analysis = _successful_analysis(message_id, model, result)
    analysis_repository.add_analysis(db, analysis)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        failure = ProviderError(
            "PERSISTENCE_ERROR",
            "AI 对比记录写入数据库失败",
            http_status=502,
            retryable=True,
            latency_ms=result.latency_ms,
            raw_response_text=result.raw_response_text,
        )
        analysis_id = _record_failure(
            db,
            message_id=message_id,
            model=model,
            error=failure,
            change_message_state=False,
            raw_result=result.value.model_dump(mode="json"),
        )
        raise AnalysisRunError(
            message_id,
            original_status,
            failure.code,
            failure.message,
            True,
            502,
            analysis_id,
        ) from exc
    return AnalyzeResponse(
        message_id=message_id,
        process_status=original_status,
        analysis_id=analysis.id,
        model_name=model,
        useful=result.value.useful,
        business_applied=False,
    )


async def _run_retry(
    db: Session, user_id: int, message_id: int, model: str
) -> AnalyzeResponse:
    now = _utc_naive()
    if not analysis_repository.claim_for_retry(db, user_id, message_id, now):
        db.rollback()
        message = analysis_repository.get_owned_message(db, user_id, message_id)
        if message is None:
            raise _run_error(message_id, MessageStatus.FAILED.value, "NOT_FOUND", "消息不存在", 404)
        raise _run_error(
            message_id,
            message.process_status,
            "INVALID_STATE",
            "消息当前状态不允许 retry，或已被其他任务处理",
            409,
        )
    db.commit()

    for attempt in range(2):
        snapshot = _prompt_snapshot(db, user_id, message_id)
        provider_messages = build_analysis_messages(*snapshot[:2], snapshot[2])
        db.rollback()
        try:
            result = await ai_service.provider().analyze(
                model=model,
                messages=provider_messages,
            )
            _validate_candidate_targets(result, snapshot[2])
        except ProviderError as exc:
            analysis_id = _record_failure(
                db,
                message_id=message_id,
                model=model,
                error=exc,
                change_message_state=True,
            )
            raise AnalysisRunError(
                message_id,
                MessageStatus.FAILED.value,
                exc.code,
                exc.message,
                exc.retryable,
                exc.http_status,
                analysis_id,
            ) from exc

        try:
            return _apply_success(
                db,
                user_id=user_id,
                message_id=message_id,
                model=model,
                result=result,
                candidates=snapshot[2],
            )
        except ConcurrentInformationUpdate as exc:
            db.rollback()
            conflict = ProviderError(
                "CONCURRENT_UPDATE",
                (
                    "候选信息已被并发修改，正在重新分析"
                    if attempt == 0
                    else "候选信息连续发生并发修改"
                ),
                http_status=409,
                retryable=True,
                latency_ms=result.latency_ms,
                raw_response_text=result.raw_response_text,
            )
            analysis_id = _record_failure(
                db,
                message_id=message_id,
                model=model,
                error=conflict,
                change_message_state=attempt == 1,
                raw_result=result.value.model_dump(mode="json"),
            )
            if attempt == 0:
                _restore_processing(db, user_id, message_id)
                continue
            raise AnalysisRunError(
                message_id,
                MessageStatus.FAILED.value,
                conflict.code,
                conflict.message,
                True,
                409,
                analysis_id,
            ) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            failure = ProviderError(
                "PERSISTENCE_ERROR",
                "AI 结果写入数据库失败",
                http_status=502,
                retryable=True,
                latency_ms=result.latency_ms,
                raw_response_text=result.raw_response_text,
            )
            analysis_id = _record_failure(
                db,
                message_id=message_id,
                model=model,
                error=failure,
                change_message_state=True,
                raw_result=result.value.model_dump(mode="json"),
            )
            raise AnalysisRunError(
                message_id,
                MessageStatus.FAILED.value,
                failure.code,
                failure.message,
                True,
                502,
                analysis_id,
            ) from exc
    raise AssertionError("retry loop must return or raise")


def _prompt_snapshot(
    db: Session, user_id: int, message_id: int
) -> tuple[Message, object, list[CandidateInformation]]:
    row = analysis_repository.get_owned_message_with_sender(db, user_id, message_id)
    if row is None:
        raise _run_error(message_id, MessageStatus.FAILED.value, "NOT_FOUND", "消息不存在", 404)
    message, sender = row
    candidates = analysis_repository.list_candidate_information(
        db,
        user_id=user_id,
        message_content=message.content,
    )
    return message, sender, candidates


def _validate_candidate_targets(
    result: ProviderResult[AIMessageOutput], candidates: list[CandidateInformation]
) -> None:
    allowed = {item.id for item in candidates}
    for item in result.value.items:
        if item.target_information_id is not None and item.target_information_id not in allowed:
            raise ProviderError(
                "INVALID_AI_OUTPUT",
                "AI 引用了候选列表之外的信息",
                http_status=502,
                retryable=True,
                latency_ms=result.latency_ms,
                raw_response_text=result.raw_response_text,
            )


def _apply_success(
    db: Session,
    *,
    user_id: int,
    message_id: int,
    model: str,
    result: ProviderResult[AIMessageOutput],
    candidates: list[CandidateInformation],
) -> AnalyzeResponse:
    candidate_versions = {item.id: item.version for item in candidates}
    analysis = _successful_analysis(message_id, model, result)
    analysis_repository.add_analysis(db, analysis)
    information_ids: list[int] = []
    for item in result.value.items:
        information_id = _apply_item(
            db,
            user_id=user_id,
            message_id=message_id,
            item=item,
            candidate_versions=candidate_versions,
        )
        information_ids.append(information_id)
    status = MessageStatus.PROCESSED.value if result.value.useful else MessageStatus.IGNORED.value
    message_update = db.execute(
        update(Message)
        .where(
            Message.id == message_id,
            Message.user_id == user_id,
            Message.process_status == MessageStatus.PROCESSING.value,
        )
        .values(process_status=status, processing_started_at=None)
    )
    if message_update.rowcount != 1:
        raise ConcurrentInformationUpdate
    db.flush()
    analysis_id = analysis.id
    db.commit()
    return AnalyzeResponse(
        message_id=message_id,
        process_status=status,
        analysis_id=analysis_id,
        model_name=model,
        useful=result.value.useful,
        information_ids=information_ids,
        business_applied=True,
    )


def _apply_item(
    db: Session,
    *,
    user_id: int,
    message_id: int,
    item: AIInformationOutput,
    candidate_versions: dict[int, int],
) -> int:
    if item.action == "create":
        information = InformationItem(
            user_id=user_id,
            title=item.title,
            summary=item.summary,
            source_type=item.source_type,
            importance=item.importance,
            confidence=Decimal(str(item.confidence)),
            status=InformationStatus.ACTIVE.value,
            version=1,
        )
        analysis_repository.add_information(db, information)
        db.flush()
    else:
        target_id = item.target_information_id
        if target_id is None or target_id not in candidate_versions:
            raise ConcurrentInformationUpdate
        information = analysis_repository.get_owned_information(db, user_id, target_id)
        if information is None:
            raise ConcurrentInformationUpdate
        if item.action in {"update", "correct"}:
            if not analysis_repository.optimistic_update_information(
                db,
                user_id=user_id,
                information_id=target_id,
                expected_version=candidate_versions[target_id],
                title=item.title,
                summary=item.summary,
                source_type=item.source_type,
                importance=item.importance,
                confidence=item.confidence,
            ):
                raise ConcurrentInformationUpdate
            db.expire(information)
    information_id = information.id
    analysis_repository.upsert_message_relation(
        db,
        user_id=user_id,
        message_id=message_id,
        information_id=information_id,
        relation_type=item.relation_type.value,
    )
    replace = item.action != "link"
    analysis_repository.set_information_categories(
        db,
        information_id=information_id,
        names=item.categories,
        replace=replace,
    )
    analysis_repository.set_information_tags(
        db,
        user_id=user_id,
        information_id=information_id,
        names=item.tags,
        replace=replace,
    )
    if item.action != "link" and item.event is not None:
        _apply_event(db, information_id, item)
    return information_id


def _apply_event(db: Session, information_id: int, item: AIInformationOutput) -> None:
    proposed = item.event
    if proposed is None:
        return
    start_at = _to_db_time(proposed.start_at)
    deadline = _to_db_time(proposed.deadline)
    event = analysis_repository.get_event(db, information_id)
    if event is None:
        event = Event(
            information_id=information_id,
            start_at=start_at,
            deadline=deadline,
            event_status=EventStatus.UPCOMING.value,
        )
        db.add(event)
        db.flush()
    else:
        event.start_at = start_at
        event.deadline = deadline
        event.event_status = EventStatus.UPCOMING.value
    _maintain_reminder(db, event, deadline)


def _maintain_reminder(db: Session, event: Event, deadline: datetime | None) -> None:
    reminder = analysis_repository.get_reminder(db, event.id)
    if deadline is None:
        if reminder is not None and not reminder.is_custom_time:
            reminder.reminder_status = ReminderStatus.DISABLED.value
        return
    remind_at = deadline - timedelta(hours=24)
    next_status = (
        ReminderStatus.DUE.value if remind_at <= _utc_naive() else ReminderStatus.PENDING.value
    )
    if reminder is None:
        db.add(
            EventReminder(
                event_id=event.id,
                remind_at=remind_at,
                reminder_status=next_status,
                is_custom_time=False,
            )
        )
        return
    if reminder.reminder_status == ReminderStatus.DISABLED.value or reminder.is_custom_time:
        return
    reminder.remind_at = remind_at
    reminder.reminder_status = next_status
    reminder.triggered_at = _utc_naive() if next_status == ReminderStatus.DUE.value else None
    reminder.read_at = None


def _successful_analysis(
    message_id: int,
    model: str,
    result: ProviderResult[AIMessageOutput],
) -> AIAnalysis:
    return AIAnalysis(
        message_id=message_id,
        model_name=model,
        status=AnalysisStatus.SUCCEEDED.value,
        useful=result.value.useful,
        latency_ms=result.latency_ms,
        raw_result=result.value.model_dump(mode="json"),
        raw_response_text=result.raw_response_text,
        analyzed_at=_utc_naive(),
    )


def _record_failure(
    db: Session,
    *,
    message_id: int,
    model: str,
    error: ProviderError,
    change_message_state: bool,
    raw_result: dict | None = None,
) -> int | None:
    db.rollback()
    analysis = AIAnalysis(
        message_id=message_id,
        model_name=model,
        status=AnalysisStatus.FAILED.value,
        useful=None,
        error_code=error.code,
        error_message=error.message[:512],
        latency_ms=error.latency_ms,
        raw_result=raw_result,
        raw_response_text=error.raw_response_text,
        analyzed_at=_utc_naive(),
    )
    analysis_repository.add_analysis(db, analysis)
    if change_message_state:
        db.execute(
            update(Message)
            .where(Message.id == message_id)
            .values(process_status=MessageStatus.FAILED.value, processing_started_at=None)
        )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return None
    return analysis.id


def _restore_processing(db: Session, user_id: int, message_id: int) -> None:
    db.execute(
        update(Message)
        .where(Message.id == message_id, Message.user_id == user_id)
        .values(
            process_status=MessageStatus.PROCESSING.value,
            processing_started_at=_utc_naive(),
        )
    )
    db.commit()


async def _compare_lock(message_id: int) -> asyncio.Lock:
    async with _compare_locks_guard:
        return _compare_locks.setdefault(message_id, asyncio.Lock())


def _run_error(
    message_id: int,
    status: str,
    code: str,
    message: str,
    http_status: int,
    *,
    retryable: bool = False,
) -> AnalysisRunError:
    return AnalysisRunError(
        message_id,
        status,
        code,
        message,
        retryable,
        http_status,
    )


def _utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _to_db_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None)




