from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    success: bool = True
    data: T | None = None
    message: str | None = None
    correlation_id: str | None = Field(default=None, alias="correlationId")


class PageMeta(BaseModel):
    """Pagination envelope (ISSUE-013)."""

    model_config = ConfigDict(populate_by_name=True)

    page: int = 1
    page_size: int = Field(20, alias="pageSize")
    total: int = 0
    total_pages: int = Field(0, alias="totalPages")
    has_next: bool = Field(False, alias="hasNext")


class PagedData(BaseModel, Generic[T]):
    """List payload plus pagination metadata (ISSUE-013)."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[T] = Field(default_factory=list)
    pagination: PageMeta


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    environment: str
    database: str = "connected"
    redis: str = "connected"
