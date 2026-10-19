"""Services and documents Pydantic schemas."""
from datetime import date
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


# ── Services ──────────────────────────────────────────────────
class ServiceRequirementOut(BaseModel):
    requirement_id: UUID
    document_type: str
    description: Optional[str] = None
    mandatory: bool = True

    class Config:
        from_attributes = True


class ServiceListItem(BaseModel):
    service_id: UUID
    service_code: Optional[str] = None
    name: str
    name_ta: Optional[str] = None
    description: Optional[str] = None
    department_name: Optional[str] = None
    category: Optional[str] = None
    government_fee: Optional[float] = None
    service_charge: Optional[float] = None
    processing_time: Optional[str] = None
    status: str = "active"
    # Only 'official_verified' may be presented as verified information.
    verification_status: str = "provisional"
    source_document_ref: Optional[str] = None
    # False until the service is official_verified: government_fee / service_charge / processing_time are then
    # unconfirmed and must not be presented to citizens as facts (e.g. never shown as "Free").
    charges_verified: bool = False

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
    gender: Optional[Literal["female", "male", "transgender", "other", "undisclosed"]] = None
    occupation: Optional[str] = None
    is_student: Optional[bool] = None
    annual_income: Optional[float] = Field(default=None, ge=0)
    social_category: Optional[str] = None
    disability_status: Optional[bool] = None
    bpl_status: Optional[bool] = None
    residence_type: Optional[Literal["rural", "urban"]] = None
    district_id: Optional[int] = None
    taluk_id: Optional[int] = None
    education_level: Optional[str] = None
    marital_status: Optional[str] = None
    family_size: Optional[int] = Field(default=None, ge=1, le=50)
    held_documents: Optional[List[str]] = None
    profile_consent: bool = False


class CitizenProfileOut(CitizenProfileIn):
    citizen_id: UUID
    full_name: Optional[str] = None

    class Config:
        from_attributes = True
