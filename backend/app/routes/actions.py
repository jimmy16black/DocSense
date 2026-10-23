import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDeniedError, ResourceNotFoundError
from app.core.security import CurrentUser, get_current_user
from app.db.session import commit_now, get_db_session
from app.models.document import Action, Document
from app.schemas.action import ActionResponse, ActionUpdateRequest, ReminderCreateRequest
from app.schemas.common import APIResponse, PagedData, PageMeta
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


@router.get("", response_model=APIResponse[PagedData[ActionResponse]])
async def list_actions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="Items per page"),
    status: str | None = Query(
        None, description="Filter by action status (PENDING, CONFIRMED, etc.)"
    ),
    search: str | None = Query(None, description="Search term in title or description"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List actions for current user with pagination and search (ISSUE-013).
    """
    base = select(Action).where(Action.user_id == current_user.id)
    if status:
        base = base.where(Action.status == status.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        base = base.where(Action.title.ilike(term) | Action.description.ilike(term))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = (
        base.order_by(Action.created_at.desc(), Action.id.desc()).offset(offset).limit(page_size)
    )
    res = await db.execute(query)
    actions = list(res.scalars().all())

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    paged: PagedData[ActionResponse] = PagedData(
        items=[ActionResponse.model_validate(a) for a in actions],
        pagination=PageMeta(
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
            hasNext=page < total_pages,
        ),
    )
    return APIResponse(success=True, data=paged)


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
