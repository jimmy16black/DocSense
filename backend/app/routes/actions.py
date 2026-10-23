import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDeniedError, ResourceNotFoundError
from app.core.security import CurrentUser, get_current_user
from app.db.session import commit_now, get_db_session
from app.models.document import Action, Document
from app.schemas.action import ActionResponse, ActionUpdateRequest, ReminderCreateRequest
from app.schemas.common import APIResponse
from app.services import audit
from app.services.idempotency import idempotency_guard, save_idempotent_response

router = APIRouter(prefix="/actions", tags=["Actions"])


@router.post(
    "/reminders",
    response_model=APIResponse[ActionResponse],
    dependencies=[Depends(idempotency_guard)],
)
async def create_reminder(
    req: ReminderCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Creates a reminder/action linked to a document.
    """
    doc_query = select(Document).where(Document.id == req.document_id)
    doc_res = await db.execute(doc_query)
    doc = doc_res.scalar_one_or_none()

    if not doc:
        raise ResourceNotFoundError("Associated document not found.")

    if doc.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    action = Action(
        document_id=req.document_id,
        user_id=current_user.id,
        action_type=req.action_type,
        title=req.title,
        description=req.description,
        due_date=req.due_date,
        status="PENDING",
        payload=req.payload,
    )
    db.add(action)
    await audit.record(
        db,
        user_id=current_user.id,
        event_type="action.created",
        document_id=req.document_id,
        details={"action_type": req.action_type},
        ip_address=audit.client_ip(request),
    )
    await commit_now(db)  # ISSUE-001: durable write before success response

    resp: APIResponse[ActionResponse] = APIResponse(
        success=True,
        data=ActionResponse.model_validate(action),
        message="Reminder created successfully.",
    )
    await save_idempotent_response(db, request, current_user.id, resp)
    return resp


@router.get("", response_model=APIResponse[list[ActionResponse]])
async def list_actions(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all pending and active actions for current user.
    """
    query = (
        select(Action).where(Action.user_id == current_user.id).order_by(Action.created_at.desc())
    )
    res = await db.execute(query)
    actions = list(res.scalars().all())

    return APIResponse(
        success=True,
        data=[ActionResponse.model_validate(a) for a in actions],
    )


@router.patch("/{action_id}", response_model=APIResponse[ActionResponse])
async def update_action(
    action_id: uuid.UUID,
    req: ActionUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update action status (e.g. mark CONFIRMED, COMPLETED, or CANCELLED).
    """
    query = select(Action).where(Action.id == action_id)
    res = await db.execute(query)
    action = res.scalar_one_or_none()

    if not action:
        raise ResourceNotFoundError("Action not found.")

    if action.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    if req.status:
        action.status = req.status
    if req.notes:
        action.payload = {**action.payload, "notes": req.notes}

    await audit.record(
        db,
        user_id=current_user.id,
        event_type="action.updated",
        document_id=action.document_id,
        action_id=action_id,
        details={"new_status": req.status},
        ip_address=audit.client_ip(request),
    )
    await commit_now(db)  # ISSUE-001: durable write before success response

    return APIResponse(
        success=True,
        data=ActionResponse.model_validate(action),
        message="Action updated successfully.",
    )
