"""Citizens API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.citizens import CitizenProfileIn, CitizenProfileOut
from app.services.citizen_service import CitizenService
from app.security.dependencies import get_current_user

router = APIRouter()


@router.get("/profile", response_model=CitizenProfileOut)
async def get_profile(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    svc = CitizenService(db)
    profile = await svc.get_profile(current_user.citizen_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile", response_model=CitizenProfileOut)
async def update_profile(
    data: CitizenProfileIn,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CitizenService(db)
    return await svc.upsert_profile(current_user.citizen_id, data)
