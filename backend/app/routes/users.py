from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db_session
from app.models.document import (
    Action,
    AuditEvent,
    ChatMessage,
    ChatSession,
    Citation,
    Document,
    DocumentChunk,
    DocumentPage,
    Extraction,
)
from app.schemas.common import APIResponse
from app.services.storage import storage_service

router = APIRouter(prefix="/users", tags=["Users"])
logger = get_logger("routes.users")


@router.delete("/me", response_model=APIResponse[dict])
async def delete_user_account(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    DPDP Right to Erasure: Purges all user data across all tables and storage.
    """
    user_id = current_user.id
    logger.info("Initiating DPDP account erasure workflow", user_id=user_id)

    # 1. Collect all storage paths to purge from R2
    doc_query = select(Document.storage_path).where(Document.user_id == user_id)
    doc_res = await db.execute(doc_query)
    storage_paths = list(doc_res.scalars().all())

    for path in storage_paths:
        storage_service.delete_file(path)

    # 2. Delete database records in cascade order
    await db.execute(delete(Citation).where(Citation.user_id == user_id))
    await db.execute(delete(Extraction).where(Extraction.user_id == user_id))
    await db.execute(delete(DocumentChunk).where(DocumentChunk.user_id == user_id))
    await db.execute(delete(DocumentPage).where(DocumentPage.user_id == user_id))
    await db.execute(delete(Action).where(Action.user_id == user_id))
    await db.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))
    await db.execute(delete(ChatSession).where(ChatSession.user_id == user_id))
    await db.execute(delete(Document).where(Document.user_id == user_id))
    await db.execute(delete(AuditEvent).where(AuditEvent.user_id == user_id))

    await db.flush()

    logger.info("DPDP account erasure completed successfully", user_id=user_id)

    return APIResponse(
        success=True,
        data={"deleted": True, "userId": user_id},
        message="All user documents, records, and data have been permanently deleted.",
    )
