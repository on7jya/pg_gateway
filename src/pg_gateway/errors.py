from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class GatewayError(Exception):
    def __init__(
        self,
        detail: str,
        *,
        code: str = "ERROR",
        status_code: int = 400,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


class ValidationAppError(GatewayError):
    def __init__(self, detail: str, *, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(detail, code=code, status_code=400)


class ForbiddenError(GatewayError):
    def __init__(self, detail: str, *, code: str = "FORBIDDEN") -> None:
        super().__init__(detail, code=code, status_code=403)


class NotFoundError(GatewayError):
    def __init__(self, detail: str = "resource not found", *, code: str = "NOT_FOUND") -> None:
        super().__init__(detail, code=code, status_code=404)


class ConflictError(GatewayError):
    def __init__(self, detail: str = "conflict", *, code: str = "CONFLICT") -> None:
        super().__init__(detail, code=code, status_code=409)


class TimeoutAppError(GatewayError):
    def __init__(self, detail: str = "query timeout", *, code: str = "TIMEOUT") -> None:
        super().__init__(detail, code=code, status_code=504)


def error_body(detail: str, code: str) -> dict[str, Any]:
    return {"detail": detail, "code": code}


async def gateway_exception_handler(_request: Request, exc: GatewayError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.detail, exc.code),
    )


async def validation_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    # FastAPI RequestValidationError
    detail = str(exc)
    errors = getattr(exc, "errors", None)
    if callable(errors):
        msgs = []
        for e in errors():
            loc = ".".join(str(x) for x in e.get("loc", ()))
            msgs.append(f"{loc}: {e.get('msg')}")
        detail = "; ".join(msgs) if msgs else detail
    return JSONResponse(status_code=400, content=error_body(detail, "VALIDATION_ERROR"))
