from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReminderCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: UUID = Field(..., alias="documentId")
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    due_date: datetime = Field(..., alias="dueDate")
    action_type: str = Field("RENEWAL_REMINDER", alias="actionType")
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str | None = None  # PENDING, CONFIRMED, COMPLETED, CANCELLED
    notes: str | None = None


class ActionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: UUID
    document_id: UUID = Field(..., alias="documentId")
    user_id: str = Field(..., alias="userId")
    action_type: str = Field(..., alias="actionType")
    title: str
    description: str | None = None
    due_date: datetime | None = Field(None, alias="dueDate")
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
