from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import DocSenseException, ErrorClassification
from app.core.logging import get_logger
from app.core.security import CurrentUser, get_current_user
from app.db.session import commit_now, get_db_session
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

    # 1. Collect all storage paths to purge from R2.
    # ISSUE-005: previously delete_file() failures were swallowed (logged only),
    # yet the API still claimed "permanently deleted" — a DPDP compliance bug.
    # Now: collect every failure and refuse to complete erasure until storage
    # is verifiably purged, returning a retryable error instead.
    doc_query = select(Document.storage_path).where(Document.user_id == user_id)
    doc_res = await db.execute(doc_query)
    storage_paths = list(doc_res.scalars().all())

    storage_failures: list[str] = []
    for path in storage_paths:
        try:
            storage_service.delete_file(path)
        except Exception as exc:
            logger.error(
                "Storage deletion failed during DPDP erasure",
                storage_path=path,
                error=str(exc),
            )
            storage_failures.append(path)

    if storage_failures:
        raise DocSenseException(
            message=(
                "Account erasure could not be completed because some files could not be "
                "deleted from secure storage. Please retry; no records were discarded."
            ),
            classification=ErrorClassification.RETRYABLE_FAILURE,
            status_code=500,
            code="ERASURE_STORAGE_FAILED",
            details={"failedPaths": len(storage_failures)},
            is_retryable=True,
        )

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

    await commit_now(db)

    # 3. Delete the identity itself (Supabase Auth user) via service-role API.
    # ISSUE-005: without this, the auth user row (email) survives in
    # auth.users — the erasure claim would be false. Best-effort but loud:
    # if identity deletion fails we must tell the operator, not silently pass.
    auth_user_deleted = await _delete_auth_user(user_id)

    logger.info(
        "DPDP account erasure completed",
        user_id=user_id,
        auth_user_deleted=auth_user_deleted,
        storage_objects_purged=len(storage_paths),
    )

    return APIResponse(
        success=True,
        data={
            "deleted": True,
            "userId": user_id,
            "authIdentityDeleted": auth_user_deleted,
        },
        message=(
            "All user documents, records, and data have been permanently deleted."
            if auth_user_deleted
            else (
                "All application data has been deleted, but the login identity "
                "could not be removed automatically. Contact support to finish erasure."
            )
        ),
    )


async def _delete_auth_user(user_id: str) -> bool:
    """Delete the Supabase Auth user via the admin API (service-role key).

    Returns True on success, False if the identity could not be removed
    (network/admin-API unavailable). Never raises — DB/storage erasure above
    is already durable; identity cleanup is reported honestly instead.
    """
    import httpx

    settings = get_settings()
    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code in (200, 204, 404):
                # 404 => user already gone; treat as success (idempotent erasure)
                return True
            logger.error(
                "Supabase admin user deletion failed",
                status_code=resp.status_code,
                body=resp.text[:500],
            )
            return False
    except Exception as exc:
        logger.error("Supabase admin user deletion errored", error=str(exc))
        return False
