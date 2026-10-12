from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class EntityNotFoundException(AppException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
        )


class QuotaExceededException(AppException):
    def __init__(self, message: str = "Active project quota exceeded. Please archive old projects."):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="QUOTA_EXCEEDED",
        )


class InsufficientCreditsException(AppException):
    def __init__(self, required: int, available: int):
        super().__init__(
            message=f"Insufficient credits. Required: {required}, Available: {available}.",
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            code="INSUFFICIENT_CREDITS",
            details={"required": required, "available": available},
        )


class CompilationException(AppException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="COMPILATION_ERROR",
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": str(exc),
                    "details": {},
                },
            },
        )
