from fastapi import HTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_502_BAD_GATEWAY,
    HTTP_503_SERVICE_UNAVAILABLE,
    HTTP_504_GATEWAY_TIMEOUT,
)

# Centralized status messages
STATUS_MESSAGES = {
    HTTP_400_BAD_REQUEST: "Bad Request",
    HTTP_401_UNAUTHORIZED: "Unauthorized",
    HTTP_403_FORBIDDEN: "Forbidden",
    HTTP_404_NOT_FOUND: "Not Found",
    HTTP_409_CONFLICT: "Conflict",
    HTTP_422_UNPROCESSABLE_CONTENT: "Unprocessable Content",
    HTTP_429_TOO_MANY_REQUESTS: "Too Many Requests",
    HTTP_500_INTERNAL_SERVER_ERROR: "Internal Server Error",
    HTTP_502_BAD_GATEWAY: "Bad Gateway",
    HTTP_503_SERVICE_UNAVAILABLE: "Service Unavailable",
    HTTP_504_GATEWAY_TIMEOUT: "Gateway Timeout",
}


def error_envelope(status_code: int, error_message: str, status_message: str | None = None) -> dict:
    """The single error body shape, matching the success envelope's flat
    snake_case keys so a client parses one shape rather than two."""
    return {
        "status_code": status_code,
        "status_message": status_message or STATUS_MESSAGES.get(status_code, "Error"),
        "error_message": error_message,
    }


class BaseAPIException(HTTPException):
    """Base exception class for all API exceptions."""

    def __init__(self, status_code: int, error_message: str):
        status_message = STATUS_MESSAGES.get(status_code, "Error")
        super().__init__(
            status_code=status_code,
            detail=error_envelope(status_code, error_message, status_message),
        )


class BadRequestAPIException(BaseAPIException):
    def __init__(self, error_message: str = "Bad request"):
        super().__init__(HTTP_400_BAD_REQUEST, error_message)


class UnauthorizedAPIException(BaseAPIException):
    def __init__(self, error_message: str = "Unauthorized"):
        super().__init__(HTTP_401_UNAUTHORIZED, error_message)


class TooManyRequestsAPIException(BaseAPIException):
    """Upstream provider rate limited us."""

    def __init__(self, error_message: str = "Too many requests, please retry shortly"):
        super().__init__(HTTP_429_TOO_MANY_REQUESTS, error_message)


class ServiceUnavailableAPIException(BaseAPIException):
    """Upstream provider (LLM, storage, tracing) is unreachable or erroring."""

    def __init__(self, error_message: str = "Upstream service unavailable, please retry shortly"):
        super().__init__(HTTP_503_SERVICE_UNAVAILABLE, error_message)


class GatewayTimeoutAPIException(BaseAPIException):
    """Upstream provider took too long to respond."""

    def __init__(self, error_message: str = "Upstream service timed out"):
        super().__init__(HTTP_504_GATEWAY_TIMEOUT, error_message)
