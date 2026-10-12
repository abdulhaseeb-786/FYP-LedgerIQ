from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[Any] = None

    @classmethod
    def ok(cls, data: T = None, message: Optional[str] = None) -> "ApiResponse[T]":
        return cls(success=True, data=data, message=message, error=None)

    @classmethod
    def fail(cls, message: str, error: Optional[Any] = None) -> "ApiResponse[None]":
        return cls(success=False, data=None, message=message, error=error)
