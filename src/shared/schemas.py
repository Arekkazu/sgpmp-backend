from typing import Optional

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class FieldError(BaseModel):
    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    fields: list[FieldError]
    timestamp: str
