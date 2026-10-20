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


@router.get("/names")
async def public_names(db: AsyncSession = Depends(get_db)) -> dict:
    """English -> Tamil display names for departments, complaint categories and districts (used to localise listings)."""
    out = {}
    for key, sql in (("departments", "SELECT department_name AS en, name_ta AS ta FROM administration.department WHERE name_ta IS NOT NULL"),
                     ("categories", "SELECT category_name AS en, name_ta AS ta FROM complaints.complaint_category WHERE name_ta IS NOT NULL"),
                     ("districts", "SELECT district_name AS en, name_ta AS ta FROM administration.district WHERE name_ta IS NOT NULL")):
        out[key] = {r.en: r.ta for r in (await db.execute(text(sql))).fetchall()}
    return out
