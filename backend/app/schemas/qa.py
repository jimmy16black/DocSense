from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.citation import CitationSchema


class AskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(..., min_length=2, max_length=1000)
    session_id: UUID | None = Field(None, alias="sessionId")


class AskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    answer: str
    confidence: str = Field(..., description="HIGH | MEDIUM | LOW | UNSUPPORTED")
    citations: list[CitationSchema] = Field(default_factory=list)
    suggested_follow_ups: list[str] = Field(default_factory=list, alias="suggestedFollowUps")
    grounded_in_evidence: bool = Field(True, alias="groundedInEvidence")


class CompareRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_ids: list[UUID] = Field(..., alias="documentIds", min_length=2, max_length=5)
    aspects: list[str] | None = Field(
        None, description="Specific terms to compare e.g. ['deductible', 'room rent limit']"
    )


class ComparisonItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    attribute: str
    values: dict[str, Any]  # document_id -> value
    winner_document_id: str | None = Field(None, alias="winnerDocumentId")
    notes: str | None = None


class CompareResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    summary: str
    comparison_matrix: list[ComparisonItem] = Field(default_factory=list, alias="comparisonMatrix")
    recommendations: list[str] = Field(default_factory=list)
