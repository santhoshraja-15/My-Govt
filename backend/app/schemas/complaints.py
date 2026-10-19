"""Complaint-related Pydantic schemas."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    category_id: Optional[int] = Field(default=None, ge=1)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)
    district_id: Optional[int] = Field(default=None, ge=1)
    is_anonymous: bool = False

    @model_validator(mode="after")
    def _both_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class ComplaintOut(BaseModel):
    complaint_id: UUID
    reference_number: str
    title: str
    status: str
    category_name: Optional[str] = None
    department_name: Optional[str] = None
    created_at: datetime
    due_date: Optional[datetime] = None
    # authority_assigned | department_level | department_only | unassigned
    assignment_state: str = "unassigned"

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
    assignment_state: str = "unassigned"
    timeline: List[ComplaintHistoryItem] = []
    sla_breached: bool = False


class ComplaintStatusUpdate(BaseModel):
    new_status: str
    remarks: Optional[str] = None
    is_public_note: bool = True


class CategoryOut(BaseModel):
    category_id: int
    name: str
    name_ta: Optional[str] = None
    description: Optional[str] = None
    default_priority: str = "medium"

    class Config:
        from_attributes = True
