"""Citizens API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.citizens import CitizenProfileIn, CitizenProfileOut
from app.services import audit
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
    request: Request,
    data: CitizenProfileIn,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CitizenService(db)
    try:
        out = await svc.upsert_profile(current_user.citizen_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    # field NAMES and the consent flag only - never profile values
    await audit.record(db, action="PROFILE_UPDATED", entity_type="citizen_profile", entity_id=str(current_user.citizen_id),
                       user=current_user, request=request,
                       new={"consent": data.profile_consent,
                            "fields_set": sorted(k for k, v in data.model_dump(exclude={"profile_consent"}).items() if v is not None)})
    return out
