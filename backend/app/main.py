import asyncio
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import (
    DocSenseException,
    ErrorClassification,
    docsense_exception_handler,
    unhandled_exception_handler,
)
from app.core.logging import (
    correlation_id_ctx,
    get_logger,
    setup_logging,
)
from app.routes import actions_router, documents_router, health_router, users_router
from app.services.pipeline import pipeline_worker, start_periodic_recovery

settings = get_settings()
setup_logging(debug=settings.DEBUG)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "DocSense Backend starting up",
        environment=settings.APP_ENV,
        version="0.1.0",
    )
    recovery_task: asyncio.Task | None = None
    # Crash-recovery sweep for documents stuck mid-pipeline after a restart
    # (ISSUE-003). Disabled under pytest where the DB is ephemeral per test.
    if os.getenv("PIPELINE_RECOVERY_ENABLED", "true").lower() in {"1", "true", "yes"} and not (
        os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules
    ):
        recovery_task = asyncio.create_task(start_periodic_recovery(), name="pipeline-recovery")
    yield
    if recovery_task is not None:
        recovery_task.cancel()
    try:
        await pipeline_worker.shutdown()
    except TimeoutError:
        logger.warning("Pipeline worker had unfinished jobs at shutdown; rows stay recoverable")
    logger.info("DocSense Backend shutting down")


app = FastAPI(
    title="DocSense API",
    description="DocSense — AI Document → Action API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# CORS Middleware
# Per W3C CORS and Fetch specification, wildcard '*' combined with allow_credentials=True
# is invalid and rejected by modern browsers. Only enable credentials for explicit origins.
cors_origins = (
    settings.ALLOWED_ORIGINS
    if isinstance(settings.ALLOWED_ORIGINS, list)
    else [settings.ALLOWED_ORIGINS]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


# Correlation ID and Request Timing Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    correlation_id_ctx.set(corr_id)

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    response.headers["X-Correlation-ID"] = corr_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

    logger.info(
        "HTTP request processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    return response


# Exception Handlers
app.add_exception_handler(DocSenseException, docsense_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    cid = correlation_id_ctx.get()
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed. Please check your request parameters.",
                "classification": ErrorClassification.USER_ACTION_REQUIRED.value,
                "isRetryable": False,
                "correlationId": cid,
                "details": {"errors": exc.errors()},
            },
        },
    )


# Routers
app.include_router(health_router)
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
app.include_router(actions_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
