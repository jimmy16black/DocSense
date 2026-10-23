from app.routes.actions import router as actions_router
from app.routes.documents import router as documents_router
from app.routes.health import router as health_router
from app.routes.users import router as users_router

__all__ = [
    "health_router",
    "documents_router",
    "actions_router",
    "users_router",
]
