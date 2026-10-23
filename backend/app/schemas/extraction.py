from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.citation import CitationSchema


class ExtractionEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    document_type: str = Field(
        ..., alias="documentType", description="Document type e.g. INSURANCE_POLICY, GST_INVOICE"
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0, alias="confidenceScore")
    title: str = Field(..., description="Document title or insurer/vendor name")
    summary_bullets: list[str] = Field(default_factory=list, alias="summaryBullets")
    important_alerts: list[str] = Field(default_factory=list, alias="importantAlerts")
    suggested_questions: list[str] = Field(default_factory=list, alias="suggestedQuestions")
    recommended_actions: list[dict[str, Any]] = Field(
        default_factory=list, alias="recommendedActions"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Structured fields specific to document type"
    )
    citations: list[CitationSchema] = Field(default_factory=list)
