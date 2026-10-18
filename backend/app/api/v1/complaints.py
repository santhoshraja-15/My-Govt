"""Complaints API endpoints."""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.complaints import (
    ComplaintCreate, ComplaintOut, ComplaintDetail,
    ComplaintListResponse, ComplaintStatusUpdate, ComplaintTrack,
)
from app.services.complaint_service import (
    ComplaintForbidden, ComplaintNotFound, ComplaintService, InvalidTransition,
)
from app.security.dependencies import get_current_user, require_role
from app.services import audit

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("", response_model=ComplaintOut, status_code=201)
async def submit_complaint(
    request: Request,
    data: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit a new civic complaint."""
    service = ComplaintService(db)
    try:
        out = await service.submit(data, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await audit.record(db, action="COMPLAINT_SUBMITTED", entity_type="complaint", entity_id=out.reference_number,
                       user=current_user, request=request,
                       new={"status": out.status, "assignment_state": out.assignment_state, "anonymous": data.is_anonymous})
    return out


@router.get("/track/{reference}", response_model=ComplaintTrack)
async def track_complaint(reference: str, db: AsyncSession = Depends(get_db)):
    """Track a complaint by reference number (public — no auth required)."""
    service = ComplaintService(db)
    result = await service.track_by_reference(reference)
    if not result:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return result


@router.get("/mine", response_model=ComplaintListResponse)
async def my_complaints(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all complaints filed by the current citizen."""
    service = ComplaintService(db)
    return await service.get_citizen_complaints(
        citizen_id=current_user.citizen_id,
        status=status, page=page, page_size=page_size
    )


@router.get("/{complaint_id}", response_model=ComplaintDetail)
async def get_complaint(
    complaint_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get full complaint detail including timeline."""
    service = ComplaintService(db)
    try:
        complaint = await service.get_complaint(complaint_id, current_user)
    except ComplaintForbidden as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.patch("/{complaint_id}/status")
async def update_status(
    request: Request,
    complaint_id: UUID,
    data: ComplaintStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["officer", "department_admin", "state_admin"])),
):
    """Update complaint status (officer/admin only)."""
    service = ComplaintService(db)
    try:
        out = await service.update_status(complaint_id, data, current_user)
    except ComplaintNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidTransition as e:
        await audit.record(db, action="COMPLAINT_STATUS_REJECTED", entity_type="complaint", entity_id=str(complaint_id),
                           user=current_user, request=request, new={"requested": data.new_status}, outcome="failure")
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await audit.record(db, action="COMPLAINT_STATUS_CHANGED", entity_type="complaint", entity_id=str(complaint_id),
                       user=current_user, request=request, new={"new_status": data.new_status})
    return out


@router.post("/{complaint_id}/evidence")
async def upload_evidence(
    complaint_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload evidence for a complaint."""
    service = ComplaintService(db)
    return await service.upload_evidence(complaint_id, file, current_user)


@router.get("/categories/list")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Get all complaint categories."""
    service = ComplaintService(db)
    return await service.get_categories()
