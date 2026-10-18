"""Scheme-related Pydantic schemas."""
from datetime import date, datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel


class EligibilityRuleOut(BaseModel):
    rule_id: UUID
    rule_group: int
    attribute: str
    operator: str
    value: Any
    unit: Optional[str] = None
    mandatory: bool = True
    human_readable: Optional[str] = None
    human_readable_ta: Optional[str] = None
    source_reference: Optional[str] = None

    class Config:
        from_attributes = True


class BenefitOut(BaseModel):
    benefit_id: UUID
    benefit_type: str
    description: Optional[str] = None
    amount: Optional[float] = None
    unit: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentRequirementOut(BaseModel):
    requirement_id: UUID
    document_type: str
    description: Optional[str] = None
    mandatory: bool = True

    class Config:
        from_attributes = True


class SchemeListItem(BaseModel):
    scheme_id: UUID
    scheme_code: str
    name: str
    name_ta: Optional[str] = None
    description: Optional[str] = None
    department_name: Optional[str] = None
    category: Optional[str] = None
    scheme_level: str
    status: str
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    verified_at: Optional[datetime] = None
    source_url: Optional[str] = None
    # Data-governance status: only 'official_verified' may be presented as verified.
    verification_status: str = "provisional"
    source_document_ref: Optional[str] = None

    class Config:
        from_attributes = True


class SchemeListResponse(BaseModel):
    items: List[SchemeListItem]
    total: int
    page: int
    page_size: int
    pages: int


class SchemeDetail(SchemeListItem):
    benefits: List[BenefitOut] = []
    eligibility_rules: List[EligibilityRuleOut] = []
    required_documents: List[DocumentRequirementOut] = []
    application_url: Optional[str] = None
    official_source_url: Optional[str] = None
    full_description: Optional[str] = None
    benefits_summary: Optional[str] = None
    notes: Optional[str] = None


# ── Eligibility Check ─────────────────────────────────────────
class EligibilityRequest(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    annual_income: Optional[float] = None
    social_category: Optional[str] = None
    disability_status: Optional[bool] = None
    bpl_status: Optional[bool] = None
    residence_type: Optional[str] = None
    district_id: Optional[int] = None
    is_student: Optional[bool] = None
    occupation: Optional[str] = None
    education_level: Optional[str] = None
    marital_status: Optional[str] = None
    family_size: Optional[int] = None
    held_documents: Optional[List[str]] = None


class RuleResult(BaseModel):
    rule_id: UUID
    attribute: str
    operator: str
    threshold: Any
    citizen_value: Any
    outcome: str   # PASS | FAIL | UNKNOWN
    reason: str
    mandatory: bool


class EligibilityResult(BaseModel):
    scheme_id: UUID
    scheme_name: str
    overall: str   # ELIGIBLE | NOT_ELIGIBLE | INSUFFICIENT_DATA
    verification_status: str = "provisional"  # of the scheme (and so of its rules)
    rule_results: List[RuleResult]
    missing_attributes: List[str]
    failing_rules: List[str]
    evaluated_at: str
    disclaimer: str = (
        "This is a preliminary automated assessment based on available information. "
        "It is not an official government determination."
    )
