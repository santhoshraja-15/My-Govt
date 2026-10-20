"""Auth, catalogue (schemes/services/departments), GIS-district and citizen-profile API paths."""
from datetime import timedelta

import pytest

from app.security.jwt import create_access_token, create_refresh_token
from tests.integration.conftest import PASSWORD, auth

pytestmark = pytest.mark.db
API = "/api/v1"


# -- auth ------------------------------------------------------------------------------
async def test_register_login_me_refresh(client, make_citizen):
    c = await make_citizen("Asha Kumar")
    assert c["user"]["role"] == "citizen" and c["user"]["citizen_id"]
    me = await client.get(f"{API}/auth/me", headers=c["headers"])
    assert me.status_code == 200
    assert me.json()["full_name"] == "Asha Kumar" and me.json()["email"] == c["email"]

    ref = await client.post(f"{API}/auth/refresh", json={"refresh_token": c["login"]["refresh_token"]})
    assert ref.status_code == 200
    assert (await client.get(f"{API}/auth/me", headers=auth(ref.json()["access_token"]))).status_code == 200


async def test_duplicate_registration_rejected(client, make_citizen):
    c = await make_citizen()
    r = await client.post(f"{API}/auth/register",
                          json={"email": c["email"], "password": PASSWORD, "full_name": "Dup"})
    assert r.status_code == 400


async def test_weak_password_rejected(client):
    r = await client.post(f"{API}/auth/register",
                          json={"email": "weak@example.com", "password": "short", "full_name": "W"})
    assert r.status_code == 422


async def test_wrong_password_401_and_counted(client, make_citizen, conn):
    c = await make_citizen()
    bad = await client.post(f"{API}/auth/login", json={"email": c["email"], "password": "wrong-password"})
    assert bad.status_code == 401
    assert await conn.fetchval("SELECT failed_logins FROM identity.app_user WHERE email=$1", c["email"]) == 1
    ok = await client.post(f"{API}/auth/login", json={"email": c["email"], "password": PASSWORD})
    assert ok.status_code == 200
    assert await conn.fetchval("SELECT failed_logins FROM identity.app_user WHERE email=$1", c["email"]) == 0


async def test_unknown_user_cannot_login(client):
    r = await client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert r.status_code == 401


async def test_expired_and_wrong_type_tokens_rejected(client, make_citizen):
    c = await make_citizen()
    uid = str(c["user"]["user_id"])
    expired = create_access_token({"sub": uid}, timedelta(seconds=-1))
    assert (await client.get(f"{API}/auth/me", headers=auth(expired))).status_code == 401
    refresh_as_access = create_refresh_token({"sub": uid})
    assert (await client.get(f"{API}/auth/me", headers=auth(refresh_as_access))).status_code == 401
    assert (await client.get(f"{API}/auth/me")).status_code == 401
    access_as_refresh = await client.post(f"{API}/auth/refresh", json={"refresh_token": c["login"]["access_token"]})
    assert access_as_refresh.status_code == 401


async def test_suspended_user_is_locked_out(client, make_citizen, conn):
    c = await make_citizen()
    await conn.execute("UPDATE identity.app_user SET status='suspended' WHERE email=$1", c["email"])
    assert (await client.get(f"{API}/auth/me", headers=c["headers"])).status_code == 401
    assert (await client.post(f"{API}/auth/login",
                              json={"email": c["email"], "password": PASSWORD})).status_code == 401


# -- schemes ---------------------------------------------------------------------------
async def test_scheme_list_is_complete_and_labelled(client):
    r = await client.get(f"{API}/schemes", params={"page_size": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 29 and len(body["items"]) == 29
    statuses = {i["verification_status"] for i in body["items"]}
    assert "official_verified" not in statuses  # nothing is verified without recorded evidence
    assert statuses <= {"provisional", "externally_referenced"}
    assert all(i["verified_at"] is None for i in body["items"] if i["verification_status"] != "official_verified")


async def test_scheme_filters(client):
    prov = (await client.get(f"{API}/schemes", params={"verification_status": "provisional", "page_size": 50})).json()
    ext = (await client.get(f"{API}/schemes", params={"verification_status": "externally_referenced"})).json()
    ver = (await client.get(f"{API}/schemes", params={"verification_status": "official_verified"})).json()
    assert prov["total"] == 28 and ext["total"] == 1 and ver["total"] == 0
    hit = (await client.get(f"{API}/schemes", params={"q": "breakfast"})).json()
    assert any("Breakfast" in i["name"] for i in hit["items"])
    assert (await client.get(f"{API}/schemes", params={"level": "state", "page_size": 50})).json()["total"] >= 1
    assert (await client.get(f"{API}/schemes", params={"page": 0})).status_code == 422


async def test_scheme_detail_and_missing(client):
    first = (await client.get(f"{API}/schemes", params={"q": "breakfast"})).json()["items"][0]
    r = await client.get(f"{API}/schemes/{first['scheme_id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["scheme_code"] == first["scheme_code"] and d["verification_status"] == "provisional"
    assert d["source_document_ref"]  # the dataset-asserted reference is shown, but status stays provisional
    assert (await client.get(f"{API}/schemes/00000000-0000-0000-0000-000000000000")).status_code == 404
    assert (await client.get(f"{API}/schemes/not-a-uuid")).status_code == 422


async def test_eligibility_without_rules_is_insufficient_data_never_eligible(client):
    s = (await client.get(f"{API}/schemes", params={"q": "breakfast"})).json()["items"][0]
    r = await client.post(f"{API}/schemes/{s['scheme_id']}/eligibility", json={"age": 30, "annual_income": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "INSUFFICIENT_DATA" and body["verification_status"] == "provisional"
    assert "not an official" in body["disclaimer"]


async def test_eligibility_engine_with_rules(client, conn):
    sid = await conn.fetchval("SELECT scheme_id FROM schemes.scheme WHERE scheme_code='TN-FREE-BUS-PASS'")
    await conn.execute("DELETE FROM schemes.eligibility_rule WHERE scheme_id=$1", sid)
    await conn.execute(
        "INSERT INTO schemes.eligibility_rule (scheme_id, rule_group, attribute, operator, value, mandatory) "
        "VALUES ($1,1,'annual_income','<=','100000'::jsonb,true), ($1,1,'age','>=','18'::jsonb,true)", sid)
    try:
        url = f"{API}/schemes/{sid}/eligibility"
        ok = (await client.post(url, json={"age": 30, "annual_income": 50000})).json()
        no = (await client.post(url, json={"age": 30, "annual_income": 500000})).json()
        unk = (await client.post(url, json={"age": 30})).json()
        assert ok["overall"] == "ELIGIBLE"
        assert no["overall"] == "NOT_ELIGIBLE" and no["failing_rules"] is not None
        assert unk["overall"] == "INSUFFICIENT_DATA" and unk["missing_attributes"] == ["annual_income"]
    finally:
        await conn.execute("DELETE FROM schemes.eligibility_rule WHERE scheme_id=$1", sid)


async def test_scheme_categories(client):
    r = await client.get(f"{API}/schemes/categories/list")
    assert r.status_code == 200 and isinstance(r.json(), list) and r.json()


# -- services / departments / districts -----------------------------------------------
async def test_service_catalogue(client):
    r = await client.get(f"{API}/services", params={"page_size": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 21
    assert {i["verification_status"] for i in body["items"]} == {"provisional"}
    assert all(i["charges_verified"] is False for i in body["items"])     # fees/timing unconfirmed until verified
    item = body["items"][0]
    d = (await client.get(f"{API}/services/{item['service_id']}")).json()
    assert d["service_id"] == item["service_id"] and "requirements" in d and d["charges_verified"] is False
    assert (await client.get(f"{API}/services", params={"verification_status": "official_verified"})).json()["total"] == 0
    assert (await client.get(f"{API}/services/00000000-0000-0000-0000-000000000000")).status_code == 404


async def test_departments(client):
    deps = (await client.get(f"{API}/departments")).json()
    assert len(deps) == 17 and {d["verification_status"] for d in deps} == {"provisional"}
    one = (await client.get(f"{API}/departments/{deps[0]['department_id']}")).json()
    assert one["department_code"] == deps[0]["department_code"]
    assert (await client.get(f"{API}/departments/99999")).status_code == 404


async def test_gis_districts_and_taluks_match_schema(client, conn):
    d = (await client.get(f"{API}/gis/districts")).json()
    assert len(d) == 38
    assert {"district_id", "district_code", "district_name", "district_name_ta", "headquarters"} <= set(d[0])
    assert next(x for x in d if x["district_code"] == "TN-CHN")["district_name_ta"] == "சென்னை"
    chennai = next(x for x in d if x["district_code"] == "TN-CHN")["district_id"]
    await conn.execute("INSERT INTO administration.taluk (district_id, name, name_ta) VALUES ($1,'Egmore-Test','எழும்பூர்')", chennai)
    try:
        t = (await client.get(f"{API}/gis/districts/{chennai}/taluks")).json()
        assert t and set(t[0]) == {"taluk_id", "taluk_name", "taluk_name_ta"} and t[0]["taluk_name"] == "Egmore-Test"
    finally:
        await conn.execute("DELETE FROM administration.taluk WHERE name='Egmore-Test'")
    assert (await client.get(f"{API}/gis/districts/9999/taluks")).json() == []


# -- citizen profile & consent ---------------------------------------------------------
async def test_profile_requires_auth(client):
    assert (await client.get(f"{API}/citizens/profile")).status_code == 401


async def test_profile_consent_lifecycle(client, make_citizen, conn):
    c = await make_citizen("Profile Person")
    h = c["headers"]
    empty = (await client.get(f"{API}/citizens/profile", headers=h)).json()
    assert empty["full_name"] == "Profile Person" and empty["profile_consent"] is False

    body = {"gender": "female", "annual_income": 120000, "residence_type": "rural", "family_size": 4,
            "education_level": "graduate", "held_documents": ["ration_card"], "profile_consent": True}
    saved = await client.put(f"{API}/citizens/profile", headers=h, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["annual_income"] == 120000 and saved.json()["profile_consent"] is True
    assert saved.json()["held_documents"] == ["ration_card"]

    revoked = await client.put(f"{API}/citizens/profile", headers=h, json={**body, "profile_consent": False})
    assert revoked.status_code == 200
    out = revoked.json()
    assert out["profile_consent"] is False and out["annual_income"] is None  # data removed with consent
    cid = c["user"]["citizen_id"]
    assert await conn.fetchval("SELECT count(*) FROM identity.consent WHERE citizen_id=$1", cid) == 2


async def test_profile_validation(client, make_citizen):
    c = await make_citizen()
    r = await client.put(f"{API}/citizens/profile", headers=c["headers"], json={"gender": "robot"})
    assert r.status_code == 422


async def test_service_and_scheme_category_lists_match_the_data_and_each_returns_results(client):
    """The filter pills are built from these lists, so every listed category must return at least one record."""
    for kind, path in (("schemes", "/api/v1/schemes"), ("services", "/api/v1/services")):
        cats = (await client.get(f"{path}/categories/list")).json()
        assert cats and cats == sorted(cats)
        for c in cats:
            body = (await client.get(path, params={"category": c})).json()
            assert body["total"] >= 1, (kind, c)


@pytest.mark.parametrize("bad", [
    {"age": -5}, {"age": 121}, {"annual_income": -1}, {"annual_income": 1e12}, {"family_size": 0}, {"family_size": 51},
    {"district_id": 0}, {"gender": "x" * 31}, {"occupation": "y" * 81}, {"age": "abc"}, {"bpl_status": "maybe"},
])
async def test_eligibility_rejects_out_of_range_or_malformed_facts(client, bad):
    sid = (await client.get("/api/v1/schemes", params={"page_size": 1})).json()["items"][0]["scheme_id"]
    assert (await client.post(f"/api/v1/schemes/{sid}/eligibility", json=bad)).status_code == 422


async def test_eligibility_accepts_boundary_values_and_unknowns(client):
    sid = (await client.get("/api/v1/schemes", params={"page_size": 1})).json()["items"][0]["scheme_id"]
    for ok in ({}, {"age": 0}, {"age": 120}, {"annual_income": 0}, {"family_size": 1}, {"family_size": 50}):
        assert (await client.post(f"/api/v1/schemes/{sid}/eligibility", json=ok)).status_code == 200, ok


# -- content completeness (migration 009 / seed 003) ----------------------------------------
async def test_every_scheme_and_service_has_both_names_and_honest_content(client):
    schemes = (await client.get(f"{API}/schemes", params={"page_size": 50})).json()["items"]
    services = (await client.get(f"{API}/services", params={"page_size": 50})).json()["items"]
    assert all(s["name"] and s["name_ta"] for s in schemes) and all(s["name"] and s["name_ta"] for s in services)
    for s in schemes:
        d = (await client.get(f"{API}/schemes/{s['scheme_id']}")).json()
        assert d["verification_status"] != "official_verified"                    # nothing is promoted by this content load
        assert d["eligibility_points"] or d["eligibility_rules"], s["name"]
        assert d["benefits"], s["name"]
        assert d["required_documents"], s["name"]
        for b in d["benefits"]:
            assert b["amount_status"] in {"verified_current", "historical", "unverified", "varies", "not_applicable"}
            if b["amount"] is not None:
                assert b["amount_status"] != "not_applicable"                      # a number always carries its confidence
        assert d["last_checked_on"] and d["source_urls"] is not None
    for v in services:
        d = (await client.get(f"{API}/services/{v['service_id']}")).json()
        assert d["requirements"], v["name"]
        assert d["fee_status"] in {"listed_official_2023", "not_listed"}
        if d["fee_status"] == "not_listed":
            assert d["government_fee"] is None and d["service_charge"] is None and d["processing_time"] is None   # nothing invented


async def test_service_requirements_are_specific_to_the_service(client):
    services = (await client.get(f"{API}/services", params={"page_size": 50})).json()["items"]
    lists = {}
    for v in services:
        d = (await client.get(f"{API}/services/{v['service_id']}")).json()
        lists[v["service_code"]] = tuple(sorted(r["document_type"] for r in d["requirements"]))
    # official lists differ per service: no two services share an identical document list unless both are the compiled fallback
    official = [k for k, v in lists.items() if any(True for _ in v)]
    assert len(set(lists[k] for k in official)) >= 15
    assert lists["SVC-COMM-CERT"] != lists["SVC-INCOME-CERT"] != lists["SVC-LEGAL-HEIR"]


async def test_policy_document_catalogue(client):
    body = (await client.get(f"{API}/documents/policy", params={"page_size": 100})).json()
    assert body["total"] == 40 and body["facets"]["categories"] == {"government_order": 8, "policy": 2, "circular": 10, "notification": 10, "act": 10}
    for d in body["items"]:
        if d["verification_status"] == "official_verified":
            assert d["pdf_url"] and d["last_checked_on"]
        assert d["summary_ta_reviewed"] is False
    assert (await client.get(f"{API}/documents/policy", params={"category": "nope"})).status_code == 422
