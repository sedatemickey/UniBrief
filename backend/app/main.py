"""FastAPI application entry point and cross-cutting API error handling."""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.errors import AppError
from app.db.session import check_database, engine
from app.services import attachment_service, task_service

_startup_tasks: set[asyncio.Task[None]] = set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Recover attachment state without blocking application startup."""

    await asyncio.to_thread(attachment_service.mark_missing_downloaded_files)
    for attachment_id in await asyncio.to_thread(attachment_service.recover_pending_downloads):
        task = asyncio.create_task(
            asyncio.to_thread(attachment_service.download_attachment, attachment_id)
        )
        _startup_tasks.add(task)
        task.add_done_callback(_startup_tasks.discard)
    periodic_tasks = [
        asyncio.create_task(task_service.periodic_event_reminder_loop()),
        asyncio.create_task(task_service.periodic_auto_analysis_loop()),
    ]
    _startup_tasks.update(periodic_tasks)
    for task in periodic_tasks:
        task.add_done_callback(_startup_tasks.discard)
    try:
        yield
    finally:
        for task in periodic_tasks:
            task.cancel()
        await asyncio.gather(*periodic_tasks, return_exceptions=True)


app = FastAPI(
    title="UniBrief API",
    version="0.1.0",
    description="校园多源消息智能聚合与信息管理系统",
    lifespan=lifespan,
)
app.include_router(api_router)


def _error_body(
    request: Request,
    *,
    code: str,
    message: str,
    retryable: bool = False,
    details: object | None = None,
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a stable request identifier to responses and error bodies."""

    request.state.request_id = request.headers.get("X-Request-ID") or uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Render expected business errors using the documented envelope."""

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(
            request,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render Pydantic failures without echoing sensitive request values."""

    details = [
        {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_body(
            request,
            code="VALIDATION_ERROR",
            message="请求参数不合法",
            details=details,
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Keep framework 404/405 errors inside the common response envelope."""

    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    message = "资源不存在" if exc.status_code == 404 else "请求无法处理"
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(request, code=code, message=message),
    )


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return a lightweight process health response."""

    return {"status": "ok", "service": "unibrief", "version": app.version}


@app.get("/api/v1/health/ready", tags=["system"], response_model=None)
def readiness() -> dict[str, object] | JSONResponse:
    """Check database readiness without returning the configured DSN."""

    try:
        status = check_database(engine)
    except (SQLAlchemyError, RuntimeError):
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "service": "unibrief",
                "database": "unavailable",
            },
        )
    return {
        "status": "ok",
        "service": "unibrief",
        "database": "ok",
        "database_version": status.version,
    }

