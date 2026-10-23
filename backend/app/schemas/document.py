from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.citation import CitationSchema
from app.schemas.extraction import ExtractionEnvelope


class DocumentUploadInitRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(..., alias="fileName", min_length=1, max_length=255)
    file_size_bytes: int = Field(..., alias="fileSizeBytes", gt=0)
    mime_type: str = Field(..., alias="mimeType")
    document_type: str | None = Field(None, alias="documentType")


class DocumentUploadInitResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: UUID = Field(..., alias="documentId")
    upload_url: str = Field(..., alias="uploadUrl")
    storage_path: str = Field(..., alias="storagePath")
    expires_at: datetime = Field(..., alias="expiresAt")


class DocumentProcessRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    force_reprocess: bool = Field(False, alias="forceReprocess")


class DocumentProcessResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(..., alias="jobId")
    document_id: UUID = Field(..., alias="documentId")
    status: str
    message: str


class DocumentPageSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    page_number: int = Field(..., alias="pageNumber")
    raw_text: str = Field(..., alias="rawText")


class DocumentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: UUID
    user_id: str = Field(..., alias="userId")
    title: str
    file_name: str = Field(..., alias="fileName")
    file_size_bytes: int = Field(..., alias="fileSizeBytes")
    mime_type: str = Field(..., alias="mimeType")
    status: str
    document_type: str | None = Field(None, alias="documentType")
    confidence_score: float | None = Field(None, alias="confidenceScore")
    page_count: int = Field(0, alias="pageCount")
    error_message: str | None = Field(None, alias="errorMessage")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    latest_extraction: ExtractionEnvelope | None = Field(None, alias="latestExtraction")
    citations: list[CitationSchema] = Field(default_factory=list)


class DocumentEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: UUID = Field(..., alias="documentId")
    status: str
    step: str
    progress_percentage: int = Field(..., alias="progressPercentage")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str | None = None


class UploadCompleteRequest(BaseModel):
    """Optional client-declared integrity data for upload verification."""

    model_config = ConfigDict(populate_by_name=True)

    checksum_sha256: str | None = Field(
        None, alias="checksumSha256", min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$"
    )


class UploadCompleteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: UUID = Field(..., alias="documentId")
    status: str
    verified_size_bytes: int = Field(..., alias="verifiedSizeBytes")
    checksum_sha256: str | None = Field(None, alias="checksumSha256")
    message: str
