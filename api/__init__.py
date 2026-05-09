from fastapi import APIRouter
from .health import router as health_router
from .patients import router as patients_router
from .diagnosis import router as diagnosis_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(patients_router, prefix="/patients", tags=["patients"])
api_router.include_router(diagnosis_router, prefix="/diagnosis", tags=["diagnosis"])
