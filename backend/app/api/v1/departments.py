"""Departments API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.department_service import DepartmentService

router = APIRouter()


@router.get("")
async def list_departments(db: AsyncSession = Depends(get_db)):
    svc = DepartmentService(db)
    return await svc.list_departments()


@router.get("/{department_id}")
async def get_department(department_id: int, db: AsyncSession = Depends(get_db)):
    svc = DepartmentService(db)
    result = await svc.get_department(department_id)
    if not result:
        raise HTTPException(status_code=404, detail="Department not found")
    return result
