from fastapi import APIRouter

from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .diagnosis import router as diagnosis_router
from .health import router as health_router
from .images import router as images_router
from .patients import router as patients_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(patients_router, prefix="/patients", tags=["patients"])
api_router.include_router(diagnosis_router, prefix="/diagnosis", tags=["diagnosis"])
api_router.include_router(images_router, prefix="/images", tags=["images"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
