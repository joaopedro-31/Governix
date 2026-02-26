from fastapi import APIRouter
from app.api.v1.routes.ai import router as ai_router

router = APIRouter(prefix="/api/v1")
router.include_router(ai_router)

# depois você inclui:
# router.include_router(auth_router)
# router.include_router(elections_router)
