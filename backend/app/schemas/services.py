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
    requirement_level: Optional[str] = None    # required | conditional | category_specific | recommended | unverified

    class Config:
        from_attributes = True


class ServiceListItem(BaseModel):
    service_id: UUID
    service_code: Optional[str] = None
    name: str
    name_ta: Optional[str] = None
    description: Optional[str] = None
    description_ta: Optional[str] = None
    fee_status: Optional[str] = None     # listed_official_2023 | unverified | not_listed
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
    responsible_department: Optional[str] = None
    eligibility_points: List[str] = []
    application_steps: List[str] = []
    how_to_apply: Optional[str] = None
    applicable_rules: Optional[str] = None
    forms: List[dict] = []
    source_urls: List[dict] = []
    last_checked_on: Optional[date] = None
    fee_note: Optional[str] = None
    processing_time_note: Optional[str] = None
    field_evidence: dict = {}


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


# ── Policy-document catalogue (documents.policy_document) ─────
class PolicyDocumentOut(BaseModel):
    policy_document_id: UUID
    doc_code: str
    category: Literal["government_order", "policy", "circular", "notification", "act"]
    identifier: Optional[str] = None
    title: str
    title_ta: Optional[str] = None
    issuing_authority: str
    issued_on: Optional[date] = None
    effective_on: Optional[date] = None
    summary_en: str
    summary_ta: Optional[str] = None
    summary_ta_reviewed: bool = False
    language: str = "en"
    related_topics: List[str] = []
    source_page_url: str
    pdf_url: Optional[str] = None
    pdf_pages: Optional[int] = None
    legal_status: Optional[str] = None
    superseded_status: str = "unknown"
    verification_status: str = "provisional"
    verification_method: Optional[str] = None
    last_checked_on: Optional[date] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class PolicyDocumentList(BaseModel):
    items: List[PolicyDocumentOut]
    total: int
    page: int
    page_size: int
    pages: int
    facets: dict = {}
