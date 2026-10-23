from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    success: bool = True
    data: T | None = None
    message: str | None = None
    correlation_id: str | None = Field(default=None, alias="correlationId")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    environment: str
    database: str = "connected"
    redis: str = "connected"
