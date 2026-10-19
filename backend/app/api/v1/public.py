"""Public, unauthenticated aggregate statistics for the landing page (live counts only)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("/stats")
async def public_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Counts of catalogue records. No personal data; synthetic records are never counted."""
    row = (await db.execute(text("""
        SELECT
          (SELECT count(*) FROM schemes.scheme WHERE status = 'active')           AS schemes,
          (SELECT count(*) FROM services.service WHERE status = 'active')         AS services,
          (SELECT count(*) FROM administration.department WHERE status = 'active') AS departments,
          (SELECT count(*) FROM administration.district)                           AS districts,
          (SELECT count(*) FROM schemes.scheme WHERE status = 'active' AND verification_status = 'official_verified') AS verified_schemes
    """))).one()
    return dict(row._mapping)
