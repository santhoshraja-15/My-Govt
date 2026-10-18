"""Pydantic schema validation, eligibility rule evaluation, chat helpers, config guard,
verification governance rules and the admin SQL guard (no database)."""
import re
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest
from app.schemas.citizens import CitizenProfileIn
from app.schemas.complaints import ComplaintCreate, ComplaintStatusUpdate
from app.schemas.gis import DistrictOut, FacilityOut, JurisdictionResult
from app.schemas.schemes import SchemeListItem
from app.services import verification as v
from app.services.admin_service import _IDENT, AdminService
from app.services.chat_service import VERIFICATION_WEIGHT, build_tsquery, compute_trust
from app.services.scheme_service import evaluate_rule

ROOT = Path(__file__).resolve().parents[3]
UUID_A = "3f2b8c1e-8a0a-4f5e-9b53-0d6f6f2f9f10"


# -- complaints ------------------------------------------------------------------------
def test_complaint_create_valid():
    c = ComplaintCreate(title="Pothole", description="Deep pothole near the bus stand", category_id="3")
    assert c.category_id == 3  # string from the HTML select is coerced to int


@pytest.mark.parametrize("kw", [
    {"title": "ab"}, {"description": "short"}, {"category_id": 0}, {"latitude": 91, "longitude": 80},
    {"latitude": 13.0}, {"longitude": 80.2}, {"district_id": -1},
])
def test_complaint_create_rejects_bad_input(kw):
    base = {"title": "Pothole", "description": "Deep pothole near the bus stand"}
    with pytest.raises(ValidationError):
        ComplaintCreate(**{**base, **kw})


def test_complaint_create_accepts_coordinates_together():
    c = ComplaintCreate(title="Pothole", description="Deep pothole near the bus stand",
                        latitude=13.08, longitude=80.27)
    assert c.latitude == 13.08


def test_status_update_defaults():
    assert ComplaintStatusUpdate(new_status="resolved").is_public_note is True


# -- auth / citizen --------------------------------------------------------------------
def test_register_password_policy():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.in", password="short", full_name="X")
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="longenough1", full_name="X")
    assert RegisterRequest(email="a@b.in", password="longenough1", full_name="X").email == "a@b.in"


def test_profile_enums_match_database_check_constraints():
    sql = (ROOT / "database/schema/001_schema.sql").read_text(encoding="utf-8")
    block = re.search(r"gender\s+text CHECK \(gender IN \((.*?)\)\)", sql).group(1)
    for g in re.findall(r"'(\w+)'", block):
        CitizenProfileIn(gender=g)
    with pytest.raises(ValidationError):
        CitizenProfileIn(gender="unknown")
    with pytest.raises(ValidationError):
        CitizenProfileIn(residence_type="suburban")


@pytest.mark.parametrize("kw", [{"annual_income": -1}, {"family_size": 0}, {"family_size": 99}])
def test_profile_numeric_bounds(kw):
    with pytest.raises(ValidationError):
        CitizenProfileIn(**kw)


def test_profile_consent_defaults_to_false():
    assert CitizenProfileIn(date_of_birth=date(1990, 1, 1)).profile_consent is False


# -- GIS / schemes ---------------------------------------------------------------------
def test_district_out_matches_service_aliases():
    d = DistrictOut(district_id=1, district_code="TN-CHN", district_name="Chennai",
                    district_name_ta="சென்னை", headquarters="Chennai")
    assert d.district_name_ta == "சென்னை"


def test_jurisdiction_result_requires_level():
    with pytest.raises(ValidationError):
        JurisdictionResult()
    assert JurisdictionResult(resolved_level="district").inside_supported_area is True


def test_facility_out_uuid_id():
    FacilityOut(facility_id=UUID_A, name="PHC")
    with pytest.raises(ValidationError):
        FacilityOut(facility_id=7, name="PHC")


def test_scheme_defaults_to_provisional_never_verified():
    s = SchemeListItem(scheme_id=UUID_A, scheme_code="X", name="X", scheme_level="state", status="active")
    assert s.verification_status == "provisional" and not v.is_verified(s.verification_status)


# -- eligibility rule evaluation -------------------------------------------------------
def rule(op, value, attr="annual_income"):
    return {"attribute": attr, "operator": op, "value": value}


@pytest.mark.parametrize("op,val,citizen,expected", [
    ("<=", 100000, 90000, "PASS"), ("<=", 100000, 100001, "FAIL"), (">=", 18, 18, "PASS"),
    (">", 18, 18, "FAIL"), ("<", 5, 4, "PASS"), ("=", "Female", "female", "PASS"),
    ("!=", "rural", "urban", "PASS"), ("IN", ["BC", "MBC"], "bc", "PASS"), ("IN", ["BC"], "SC", "FAIL"),
    ("NOT_IN", ["SC"], "BC", "PASS"), ("BETWEEN", [18, 60], 40, "PASS"), ("BETWEEN", [18, 60], 61, "FAIL"),
    ("IS_TRUE", None, True, "PASS"), ("IS_TRUE", None, False, "FAIL"), ("IS_FALSE", None, False, "PASS"),
])
def test_evaluate_rule(op, val, citizen, expected):
    assert evaluate_rule(rule(op, val, "x"), {"x": citizen}) == expected


def test_missing_attribute_is_unknown_never_assumed():
    assert evaluate_rule(rule("<=", 1), {}) == "UNKNOWN"
    assert evaluate_rule(rule("<=", 1), {"annual_income": None}) == "UNKNOWN"


def test_malformed_values_are_unknown():
    assert evaluate_rule(rule("<=", "abc"), {"annual_income": 5}) == "UNKNOWN"
    assert evaluate_rule(rule("BETWEEN", [1]), {"annual_income": 5}) == "UNKNOWN"
    assert evaluate_rule(rule("??", 1), {"annual_income": 5}) == "UNKNOWN"


def test_jsonb_value_given_as_text_is_decoded():
    assert evaluate_rule(rule("IN", '["BC","MBC"]'), {"annual_income": "BC"}) == "PASS"


# -- chat helpers ----------------------------------------------------------------------
def test_tsquery_drops_stopwords_and_unsafe_chars():
    q = build_tsquery("What benefits do disabled persons get? ; DROP TABLE x --")
    assert q == "benefits | disabled | persons | drop | table"
    assert build_tsquery("a an the of") is None
    assert "'" not in (build_tsquery("obrien's scheme") or "")


def test_tsquery_keeps_tamil_words():
    assert "திட்டம்" in build_tsquery("மகளிர் திட்டம் பற்றி")


def test_trust_weights_verification():
    official = compute_trust([{"reliability_score": 1.0, "verification_status": "official_verified"}])
    prov = compute_trust([{"reliability_score": 1.0, "verification_status": "provisional"}])
    assert official == 1.0 and prov == VERIFICATION_WEIGHT["provisional"] < official
    assert compute_trust([]) == 0.0


# -- verification governance -----------------------------------------------------------
def test_verification_vocabulary_matches_migration_check():
    sql = (ROOT / "database/migrations/002_provenance_and_audit_fixes.sql").read_text(encoding="utf-8")
    block = re.search(r"verification_status IN \((.*?)\)", sql).group(1)
    assert set(re.findall(r"'(\w+)'", block)) == set(v.STATUSES)


@pytest.mark.parametrize("old,new,ref,ok", [
    ("provisional", "official_verified", "GO Ms 12/2024", True),
    ("provisional", "official_verified", None, False),
    ("provisional", "official_verified", "   ", False),
    ("official_verified", "provisional", None, True),   # demotion never needs evidence
    ("unverified", "externally_referenced", None, True),
    ("provisional", "deprecated", None, True),
    ("deprecated", "provisional", "ref", False),
    ("deprecated", "deprecated", None, True),
    ("provisional", "bogus", "ref", False),
    (None, "provisional", None, True),
    (None, "official_verified", None, False),
])
def test_validate_transition(old, new, ref, ok):
    if ok:
        v.validate_transition(old, new, ref)
    else:
        with pytest.raises(ValueError):
            v.validate_transition(old, new, ref)


def test_only_official_verified_counts_as_verified():
    assert [s for s in v.STATUSES if v.is_verified(s)] == ["official_verified"]


# -- config & admin guards -------------------------------------------------------------
def test_production_rejects_placeholder_secrets():
    from app.core.config import Settings

    with pytest.raises(ValueError, match="Insecure placeholder secrets"):
        Settings(APP_ENV="production")
    ok = Settings(APP_ENV="production", JWT_SECRET_KEY="x" * 48, POSTGRES_PASSWORD="strong-db-password",
                  NEO4J_PASSWORD="strong-neo4j-pw", MINIO_SECRET_KEY="strong-minio-secret")
    assert ok.APP_ENV == "production"
    Settings(APP_ENV="development")  # defaults remain fine for local development


@pytest.mark.parametrize("sql", [
    "DELETE FROM audit.audit_log", "drop table x", "SELECT 1; SELECT 2", "UPDATE x SET a=1",
    "SELECT pg_read_file('/etc/passwd')", "COPY x TO '/tmp/y'",
])
@pytest.mark.asyncio
async def test_admin_query_guard_blocks_unsafe_sql(sql):
    out = await AdminService(db=None).run_safe_query(sql)  # rejected before any DB access
    assert "error" in out


@pytest.mark.asyncio
async def test_admin_query_guard_blocks_credential_columns_and_non_select():
    svc = AdminService(db=None)
    assert "error" in await svc.run_safe_query("SELECT password_hash FROM identity.app_user")
    assert "error" in await svc.run_safe_query("VACUUM")
    assert "error" in await svc.run_safe_query("")
    assert "error" in await svc.run_safe_query("SELECT " + "x" * 6000)


def test_identifier_pattern():
    assert _IDENT.fullmatch("app_user")
    assert not _IDENT.fullmatch('x";drop')
    assert not _IDENT.fullmatch("Bad")
