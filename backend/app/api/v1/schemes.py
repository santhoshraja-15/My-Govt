"""Schemes API endpoints."""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.schemes import (
    SchemeListResponse, SchemeDetail, EligibilityRequest, EligibilityResult
)
from app.services.scheme_service import SchemeService
from app.security.dependencies import get_current_user_optional

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("", response_model=SchemeListResponse)
async def list_schemes(
    q: Optional[str] = Query(None, description="Keyword search"),
    department_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None, description="central|state|district"),
    status: str = Query("active"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search and list government schemes with filters."""
    service = SchemeService(db)
    return await service.list_schemes(
        q=q, department_id=department_id, category=category,
        level=level, status=status, page=page, page_size=page_size
    )


@router.get("/{scheme_id}", response_model=SchemeDetail)
async def get_scheme(scheme_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get full details of a specific scheme."""
    service = SchemeService(db)
    scheme = await service.get_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


@router.post("/{scheme_id}/eligibility", response_model=EligibilityResult)
async def check_eligibility(
    scheme_id: UUID,
    profile: EligibilityRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Run deterministic eligibility check for a scheme against a citizen profile."""
    service = SchemeService(db)
    scheme = await service.get_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    result = await service.check_eligibility(scheme_id, profile, current_user)
    return result


@router.get("/categories/list")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Get all scheme categories."""
    service = SchemeService(db)
    return await service.get_categories()
