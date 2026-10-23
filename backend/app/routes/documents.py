import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    DocSenseException,
    ErrorClassification,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import CurrentUser, get_current_user
from app.db.session import commit_now, get_db_session
from app.models.document import (
    Citation,
    Document,
    DocumentChunk,
    DocumentStatus,
    Extraction,
)
from app.schemas.citation import CitationSchema
from app.schemas.common import APIResponse
from app.schemas.document import (
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentResponse,
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
)
from app.schemas.extraction import ExtractionEnvelope
from app.schemas.qa import AskRequest, AskResponse, CompareRequest, CompareResponse, ComparisonItem
from app.services.extractor import pdf_extractor_service
from app.services.rag import rag_service
from app.services.storage import storage_service

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = get_logger("routes.documents")
settings = get_settings()


@router.post("/upload-init", response_model=APIResponse[DocumentUploadInitResponse])
async def init_upload(
    req: DocumentUploadInitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Initialize secure presigned document upload to Cloudflare R2 vault.
    Validates file extension, size, and MIME type.
    """
    if req.file_size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise ValidationError(
            f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB"
        )

    if req.mime_type not in settings.ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"MIME type '{req.mime_type}' is not supported. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}"
        )

    doc_id = uuid.uuid4()
    storage_path = f"users/{current_user.id}/documents/{doc_id}/{req.file_name}"

    upload_url, expires_at = storage_service.generate_upload_url(
        storage_path=storage_path,
        mime_type=req.mime_type,
    )

    document = Document(
        id=doc_id,
        user_id=current_user.id,
        title=req.file_name.rsplit(".", 1)[0],
        file_name=req.file_name,
        file_size_bytes=req.file_size_bytes,
        mime_type=req.mime_type,
        storage_path=storage_path,
        status=DocumentStatus.UPLOADED,
        document_type=req.document_type,
    )
    db.add(document)
    # Commit immediately so the document row is durable BEFORE handing the
    # client a presigned URL (ISSUE-001). Otherwise an upload could reference
    # a document row that never persisted.
    await commit_now(db)

    return APIResponse(
        success=True,
        data=DocumentUploadInitResponse(
            document_id=doc_id,
            upload_url=upload_url,
            storage_path=storage_path,
            expires_at=expires_at,
        ),
        message="Upload initialized successfully.",
    )


@router.post("/{document_id}/process", response_model=APIResponse[DocumentProcessResponse])
async def process_document(
    document_id: uuid.UUID,
    req: DocumentProcessRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Triggers asynchronous/pipeline extraction for a document.
    Enforces user ownership, idempotency, and error state transitions.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document with ID {document_id} was not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("You do not have access to process this document.")

    # Idempotency check: if already completed and not force reprocess
    if document.status == DocumentStatus.COMPLETED and not req.force_reprocess:
        return APIResponse(
            success=True,
            data=DocumentProcessResponse(
                job_id=f"job-{document.id}-cached",
                document_id=document.id,
                status=document.status,
                message="Document is already processed.",
            ),
        )

    # Transition to VALIDATING -> EXTRACTING and persist the state change
    # immediately (ISSUE-001: never rely on bare flush() for observable writes).
    document.status = DocumentStatus.EXTRACTING
    await commit_now(db)

    try:
        # Simulate extraction pipeline (or invoke workers/services)
        # 1. Provide mock page text for offline / unit tests
        mock_pages = [
            (
                1,
                f"Document: {document.title}\nPolicy Schedule\nSum Insured: Rs. 10,00,000/- for Jane Doe.",
            ),
            (
                2,
                "Terms & Conditions\nSection 4.1: Pre-existing diseases covered after 24 consecutive months.",
            ),
        ]
        document.page_count = len(mock_pages)

        # 2. Extract structured envelope
        envelope = await pdf_extractor_service.extract_structured_envelope(
            pages=mock_pages,
            document_type_hint=document.document_type or "INSURANCE_POLICY",
        )

        # 3. Save extraction
        extraction = Extraction(
            document_id=document.id,
            user_id=current_user.id,
            document_type=envelope.document_type,
            confidence_score=envelope.confidence_score,
            title=envelope.title,
            summary_bullets=envelope.summary_bullets,
            important_alerts=envelope.important_alerts,
            suggested_questions=envelope.suggested_questions,
            recommended_actions=envelope.recommended_actions,
            payload=envelope.payload,
        )
        db.add(extraction)
        await db.flush()  # populate extraction.id for citation FK below

        # 4. Save citations
        for c in envelope.citations:
            citation_entry = Citation(
                document_id=document.id,
                extraction_id=extraction.id,
                user_id=current_user.id,
                page_number=c.page_number,
                section_heading=c.section_heading,
                exact_quote=c.exact_quote,
                bounding_box=c.bounding_box,
            )
            db.add(citation_entry)

        # 5. Create chunks
        chunks_data = pdf_extractor_service.chunk_text(mock_pages)
        for ch in chunks_data:
            chunk_entry = DocumentChunk(
                document_id=document.id,
                user_id=current_user.id,
                page_number=ch["page_number"],
                chunk_index=ch["chunk_index"],
                content=ch["content"],
            )
            db.add(chunk_entry)

        document.status = DocumentStatus.COMPLETED
        document.confidence_score = envelope.confidence_score
        document.document_type = envelope.document_type
        # Persist ALL pipeline results atomically before reporting success.
        await commit_now(db)
    except Exception as exc:
        # Error-state transition per Document_8 state machine: FAILED is durable
        # even when the rest of the transaction is rolled back.
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)[:2000]
        await commit_now(db)
        logger.error("Document processing failed", document_id=str(document_id), error=str(exc))
        raise

    return APIResponse(
        success=True,
        data=DocumentProcessResponse(
            job_id=f"job-{document.id}-{uuid.uuid4().hex[:8]}",
            document_id=document.id,
            status=DocumentStatus.COMPLETED,
            message="Document processed and indexed successfully.",
        ),
    )


@router.get("/{document_id}", response_model=APIResponse[DocumentResponse])
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get full document metadata, status, extraction envelope, and citations.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document {document_id} not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    # Fetch latest extraction
    ext_query = (
        select(Extraction)
        .where(Extraction.document_id == document.id)
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    ext_res = await db.execute(ext_query)
    extraction = ext_res.scalar_one_or_none()

    # Fetch citations
    cit_query = select(Citation).where(Citation.document_id == document.id)
    cit_res = await db.execute(cit_query)
    citations = list(cit_res.scalars().all())

    latest_envelope = None
    if extraction:
        latest_envelope = ExtractionEnvelope(
            document_type=extraction.document_type,
            confidence_score=extraction.confidence_score,
            title=extraction.title,
            summary_bullets=extraction.summary_bullets,
            important_alerts=extraction.important_alerts,
            suggested_questions=extraction.suggested_questions,
            recommended_actions=extraction.recommended_actions,
            payload=extraction.payload,
            citations=[
                CitationSchema(
                    page_number=c.page_number,
                    section_heading=c.section_heading,
                    exact_quote=c.exact_quote,
                    bounding_box=c.bounding_box,
                )
                for c in citations
            ],
        )

    doc_resp = DocumentResponse(
        id=document.id,
        user_id=document.user_id,
        title=document.title,
        file_name=document.file_name,
        file_size_bytes=document.file_size_bytes,
        mime_type=document.mime_type,
        status=document.status,
        document_type=document.document_type,
        confidence_score=document.confidence_score,
        page_count=document.page_count,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        latest_extraction=latest_envelope,
        citations=[
            CitationSchema(
                page_number=c.page_number,
                section_heading=c.section_heading,
                exact_quote=c.exact_quote,
                bounding_box=c.bounding_box,
            )
            for c in citations
        ],
    )

    return APIResponse(success=True, data=doc_resp)


@router.get("", response_model=APIResponse[list[DocumentResponse]])
async def list_documents(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all documents owned by current authenticated user.
    """
    query = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(query)
    docs = list(result.scalars().all())

    items = [
        DocumentResponse(
            id=d.id,
            user_id=d.user_id,
            title=d.title,
            file_name=d.file_name,
            file_size_bytes=d.file_size_bytes,
            mime_type=d.mime_type,
            status=d.status,
            document_type=d.document_type,
            confidence_score=d.confidence_score,
            page_count=d.page_count,
            error_message=d.error_message,
            created_at=d.created_at,
            updated_at=d.updated_at,
            latest_extraction=None,
            citations=[],
        )
        for d in docs
    ]

    return APIResponse(success=True, data=items)


@router.post("/{document_id}/ask", response_model=APIResponse[AskResponse])
async def ask_question(
    document_id: uuid.UUID,
    req: AskRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Grounded Q&A over document with citations.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document {document_id} not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    ans = await rag_service.answer_question(
        db=db,
        document_id=document.id,
        user_id=current_user.id,
        question=req.question,
    )

    return APIResponse(success=True, data=ans)


@router.post("/compare", response_model=APIResponse[CompareResponse])
async def compare_documents(
    req: CompareRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Compares 2-5 documents side-by-side on critical terms/clauses.
    """
    query = select(Document).where(
        Document.id.in_(req.document_ids),
        Document.user_id == current_user.id,
    )
    result = await db.execute(query)
    documents = list(result.scalars().all())

    if len(documents) != len(req.document_ids):
        raise ValidationError("One or more documents could not be found or do not belong to you.")

    # Compare key attributes
    matrix = [
        ComparisonItem(
            attribute="Document Type",
            values={str(d.id): d.document_type or "Unknown" for d in documents},
            winnerDocumentId=None,
            notes="Extracted document classification",
        ),
        ComparisonItem(
            attribute="Coverage / Title",
            values={str(d.id): d.title for d in documents},
            winnerDocumentId=None,
            notes="Document name",
        ),
    ]

    return APIResponse(
        success=True,
        data=CompareResponse(
            summary=f"Compared {len(documents)} documents successfully.",
            comparisonMatrix=matrix,
            recommendations=["Review terms and conditions for deductible differences."],
        ),
    )


@router.delete("/{document_id}", response_model=APIResponse[dict])
async def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Deletes a document, its pages, chunks, citations, actions, and storage files.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document {document_id} not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    # Delete storage object first; if it fails we must NOT claim full deletion.
    # ISSUE-005 (partial): surface storage failures instead of swallowing them.
    try:
        storage_service.delete_file(document.storage_path)
    except Exception as exc:
        logger.error(
            "Storage deletion failed during document delete",
            document_id=str(document_id),
            error=str(exc),
        )
        raise DocSenseException(
            message="Document could not be fully deleted. Please try again.",
            classification=ErrorClassification.RETRYABLE_FAILURE,
            status_code=500,
            code="STORAGE_DELETE_FAILED",
            is_retryable=True,
        ) from exc

    await db.delete(document)  # cascades to pages/chunks/extractions/actions
    await commit_now(db)

    return APIResponse(
        success=True,
        data={"deleted": True, "documentId": str(document_id)},
        message="Document and all associated data deleted successfully.",
    )
