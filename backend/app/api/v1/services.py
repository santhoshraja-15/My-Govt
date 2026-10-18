"""Services (e-Sevai etc.) API endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.services import ServiceListResponse, ServiceDetail
from app.services.service_service import ServiceService

router = APIRouter()


@router.get("", response_model=ServiceListResponse)
async def list_services(
    q: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = ServiceService(db)
    return await svc.list_services(q=q, department_id=department_id,
                                    category=category, page=page, page_size=page_size)


@router.get("/{service_id}", response_model=ServiceDetail)
async def get_service(service_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = ServiceService(db)
    result = await svc.get_service(service_id)
    if not result:
        raise HTTPException(status_code=404, detail="Service not found")
    return result
