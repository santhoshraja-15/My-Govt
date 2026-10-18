"""API v1 router — aggregates all domain routers."""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.schemes import router as schemes_router
from app.api.v1.services import router as services_router
from app.api.v1.documents import router as documents_router
from app.api.v1.complaints import router as complaints_router
from app.api.v1.chat import router as chat_router
from app.api.v1.gis import router as gis_router
from app.api.v1.admin import router as admin_router
from app.api.v1.citizens import router as citizens_router
from app.api.v1.departments import router as departments_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(citizens_router, prefix="/citizens", tags=["Citizens"])
router.include_router(departments_router, prefix="/departments", tags=["Departments"])
router.include_router(schemes_router, prefix="/schemes", tags=["Schemes"])
router.include_router(services_router, prefix="/services", tags=["Services"])
router.include_router(documents_router, prefix="/documents", tags=["Documents"])
router.include_router(complaints_router, prefix="/complaints", tags=["Complaints"])
router.include_router(chat_router, prefix="/chat", tags=["AI Assistant"])
router.include_router(gis_router, prefix="/gis", tags=["GIS"])
router.include_router(admin_router, prefix="/admin", tags=["Administration"])
