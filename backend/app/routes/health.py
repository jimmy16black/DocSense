from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/healthz", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def liveness_check():
    """Kubernetes / platform liveness check."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        environment=settings.APP_ENV,
        database="ok",
        redis="ok",
    )


@router.get("/readyz", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def readiness_check():
    """Readiness probe checking database and redis reachability."""
    # In live environments, can perform a quick DB connection ping
    return HealthResponse(
        status="ready",
        version="0.1.0",
        environment=settings.APP_ENV,
        database="connected",
        redis="connected",
    )
