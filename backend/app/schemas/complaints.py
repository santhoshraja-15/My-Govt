"""Complaint-related Pydantic schemas."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class ComplaintCreate(BaseModel):
    title: str
    description: str
    category_id: Optional[UUID] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    district_id: Optional[int] = None
    is_anonymous: bool = False


class ComplaintOut(BaseModel):
    complaint_id: UUID
    reference_number: str
    title: str
    status: str
    category_name: Optional[str] = None
    department_name: Optional[str] = None
    created_at: datetime
    due_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComplaintHistoryItem(BaseModel):
    changed_at: datetime
    old_status: Optional[str]
    new_status: str
    remarks: Optional[str]
    changed_by_role: Optional[str]

    class Config:
        from_attributes = True


class ComplaintDetail(ComplaintOut):
    description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    priority: Optional[str] = None
    authority_name: Optional[str] = None
    officer_name: Optional[str] = None
    escalation_due_at: Optional[datetime] = None
    timeline: List[ComplaintHistoryItem] = []
    ai_confidence: Optional[float] = None
    ai_category: Optional[str] = None


class ComplaintListResponse(BaseModel):
    items: List[ComplaintOut]
    total: int
    page: int
    page_size: int
    pages: int


class ComplaintTrack(BaseModel):
    reference_number: str
    title: str
    status: str
    category_name: Optional[str] = None
    department_name: Optional[str] = None
    authority_name: Optional[str] = None
    created_at: datetime
    due_date: Optional[datetime] = None
    timeline: List[ComplaintHistoryItem] = []
    sla_breached: bool = False


class ComplaintStatusUpdate(BaseModel):
    new_status: str
    remarks: Optional[str] = None
    is_public_note: bool = True


class CategoryOut(BaseModel):
    category_id: UUID
    name: str
    name_ta: Optional[str] = None
    description: Optional[str] = None
    default_priority: str = "medium"

    class Config:
        from_attributes = True
