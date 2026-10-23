from enum import Enum
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.logging import correlation_id_ctx, get_logger

logger = get_logger("errors")


class ErrorClassification(str, Enum):
    SUCCESS = "SUCCESS"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"
    SYSTEM_FAILURE = "SYSTEM_FAILURE"


class DocSenseException(Exception):
    def __init__(
        self,
        message: str,
        classification: ErrorClassification = ErrorClassification.SYSTEM_FAILURE,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        details: dict[str, Any] | None = None,
        is_retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.classification = classification
        self.status_code = status_code
        self.code = code
        self.details = details or {}
        self.is_retryable = is_retryable


class AuthenticationError(DocSenseException):
    def __init__(self, message: str = "Invalid or expired authentication credentials"):
        super().__init__(
            message=message,
            classification=ErrorClassification.USER_ACTION_REQUIRED,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_FAILED",
            is_retryable=False,
        )


class PermissionDeniedError(DocSenseException):
    def __init__(self, message: str = "Access denied for this resource"):
        super().__init__(
            message=message,
            classification=ErrorClassification.USER_ACTION_REQUIRED,
            status_code=status.HTTP_403_FORBIDDEN,
            code="PERMISSION_DENIED",
            is_retryable=False,
        )


class ResourceNotFoundError(DocSenseException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            classification=ErrorClassification.PERMANENT_FAILURE,
            status_code=status.HTTP_404_NOT_FOUND,
            code="RESOURCE_NOT_FOUND",
            is_retryable=False,
        )


class ValidationError(DocSenseException):
    def __init__(
        self, message: str = "Input validation failed", details: dict[str, Any] | None = None
    ):
        super().__init__(
            message=message,
            classification=ErrorClassification.USER_ACTION_REQUIRED,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            details=details,
            is_retryable=False,
        )


class RateLimitExceededError(DocSenseException):
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            message=message,
            classification=ErrorClassification.RETRYABLE_FAILURE,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
            is_retryable=True,
        )


class GatewayTimeoutError(DocSenseException):
    def __init__(self, message: str = "AI Gateway service request timed out"):
        super().__init__(
            message=message,
            classification=ErrorClassification.RETRYABLE_FAILURE,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code="GATEWAY_TIMEOUT",
            is_retryable=True,
        )


async def docsense_exception_handler(request: Request, exc: DocSenseException) -> JSONResponse:
    cid = correlation_id_ctx.get()
    logger.warning(
        "Handled DocSense error",
        error_code=exc.code,
        classification=exc.classification.value,
        status_code=exc.status_code,
        path=request.url.path,
        message=exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "classification": exc.classification.value,
                "isRetryable": exc.is_retryable,
                "correlationId": cid,
                "details": exc.details,
            },
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    cid = correlation_id_ctx.get()
    logger.error(
        "Unhandled system failure",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    # Never leak internal stack traces or database info to client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while processing your request.",
                "classification": ErrorClassification.SYSTEM_FAILURE.value,
                "isRetryable": True,
                "correlationId": cid,
                "details": {},
            },
        },
    )
