"""GIS-related Pydantic schemas."""
from typing import Optional
from pydantic import BaseModel


class JurisdictionResult(BaseModel):
    ward_id: Optional[int] = None
    ward_name: Optional[str] = None
    local_body_id: Optional[int] = None
    local_body_name: Optional[str] = None
    local_body_type: Optional[str] = None
    taluk_id: Optional[int] = None
    taluk_name: Optional[str] = None
    district_id: Optional[int] = None
    district_name: Optional[str] = None
    state_name: str = "Tamil Nadu"
    resolved_level: str   # ward | local_body | taluk | district
    inside_supported_area: bool = True


class DistrictOut(BaseModel):
    district_id: int
    district_code: str
    district_name: str
    district_name_ta: Optional[str] = None
    headquarters: Optional[str] = None

    class Config:
        from_attributes = True


class FacilityOut(BaseModel):
    facility_id: int
    name: str
    facility_type: str
    department_name: Optional[str] = None
    address: Optional[str] = None
    district_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True
