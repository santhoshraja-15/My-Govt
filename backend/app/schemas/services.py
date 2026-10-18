"""Services and documents Pydantic schemas."""
from datetime import date
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


# ── Services ──────────────────────────────────────────────────
class ServiceRequirementOut(BaseModel):
    requirement_id: UUID
    document_type: str
    description: str
    mandatory: bool = True

    class Config:
        from_attributes = True


class ServiceListItem(BaseModel):
    service_id: UUID
    service_code: str
    name: str
    name_ta: Optional[str] = None
    description: Optional[str] = None
    department_name: Optional[str] = None
    category: Optional[str] = None
    government_fee: Optional[float] = None
    service_charge: Optional[float] = None
    processing_days: Optional[int] = None
    status: str = "active"

    class Config:
        from_attributes = True


class ServiceListResponse(BaseModel):
    items: List[ServiceListItem]
    total: int
    page: int
    page_size: int
    pages: int


class ServiceDetail(ServiceListItem):
    requirements: List[ServiceRequirementOut] = []
    application_url: Optional[str] = None
    official_source_url: Optional[str] = None
    notes: Optional[str] = None


# ── Documents ─────────────────────────────────────────────────
class DocumentListItem(BaseModel):
    document_id: UUID
    title: str
    doc_type: str
    department_name: Optional[str] = None
    language: str = "en"
    publication_date: Optional[date] = None
    effective_date: Optional[date] = None
    status: str = "active"
    source_url: Optional[str] = None
    verified_at: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: List[DocumentListItem]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentDetail(DocumentListItem):
    extracted_text: Optional[str] = None
    summary: Optional[str] = None
    expiry_date: Optional[date] = None
    file_hash: Optional[str] = None
    chunk_count: int = 0


# ── Citizens ──────────────────────────────────────────────────
class CitizenProfileIn(BaseModel):
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    is_student: Optional[bool] = None
    annual_income: Optional[float] = None
    social_category: Optional[str] = None
    disability_status: Optional[bool] = None
    bpl_status: Optional[bool] = None
    residence_type: Optional[str] = None
    district_id: Optional[int] = None
    taluk_id: Optional[int] = None
    education_level: Optional[str] = None
    marital_status: Optional[str] = None
    family_size: Optional[int] = None
    held_documents: Optional[List[str]] = None
    profile_consent: bool = False


class CitizenProfileOut(CitizenProfileIn):
    citizen_id: UUID
    full_name: Optional[str] = None

    class Config:
        from_attributes = True
