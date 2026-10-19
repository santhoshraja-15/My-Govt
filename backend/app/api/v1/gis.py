"""GIS and jurisdiction API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.gis import DistrictOut, FacilityOut, JurisdictionResult
from app.services.gis_service import GISService

router = APIRouter()


@router.get("/resolve-jurisdiction", response_model=JurisdictionResult)
async def resolve_jurisdiction(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a lat/lon coordinate to its administrative jurisdiction."""
    svc = GISService(db)
    result = await svc.resolve_jurisdiction(lat=lat, lon=lon)
    if not result:
        raise HTTPException(status_code=404, detail="Location outside supported area")
    return result


@router.get("/districts", response_model=list[DistrictOut])
async def list_districts(db: AsyncSession = Depends(get_db)):
    """Get all Tamil Nadu districts."""
    svc = GISService(db)
    return await svc.get_districts()


@router.get("/districts/{district_id}/taluks")
async def get_taluks(district_id: int, db: AsyncSession = Depends(get_db)):
    """Get taluks for a district."""
    svc = GISService(db)
    return await svc.get_taluks(district_id)


@router.get("/facilities", response_model=list[FacilityOut])
async def get_nearby_facilities(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(5.0, ge=0.1, le=50),
    facility_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get nearby government facilities within radius."""
    svc = GISService(db)
    return await svc.get_nearby_facilities(lat=lat, lon=lon,
                                             radius_km=radius_km,
                                             facility_type=facility_type)
