"""Complaint API: validation, routing, SLA, authorization, status transitions, scheduler."""
from datetime import datetime, timedelta

import pytest

from app.jobs.scheduler import escalate_overdue_complaints

pytestmark = pytest.mark.db
API = "/api/v1/complaints"
BODY = {"title": "Pothole on main road", "description": "A deep pothole near the bus stand causing accidents"}


async def _make_category(conn, code: str, dept: int, priority="critical", hours=100):
    cid = await conn.fetchval(
        "INSERT INTO complaints.complaint_category (category_code, category_name, default_department_id, "
        "default_priority, default_sla_hours) VALUES ($1,$1,$2,$3,$4) RETURNING category_id",
        code, dept, priority, hours)
    return cid


async def _submit(client, headers, **extra):
    r = await client.post(API, headers=headers, json={**BODY, **extra})
    assert r.status_code == 201, r.text
    return r.json()


# -- submission / validation -----------------------------------------------------------
async def test_submission_requires_authentication(client):
    assert (await client.post(API, json=BODY)).status_code == 401


@pytest.mark.parametrize("extra", [
    {"title": "x"}, {"latitude": 13.0}, {"latitude": 123.0, "longitude": 80.0}, {"category_id": "abc"},
])
async def test_invalid_submission_is_422(client, make_citizen, extra):
    c = await make_citizen()
    assert (await client.post(API, headers=c["headers"], json={**BODY, **extra})).status_code == 422


async def test_unknown_category_is_400(client, make_citizen):
    c = await make_citizen()
    r = await client.post(API, headers=c["headers"], json={**BODY, "category_id": 99999})
    assert r.status_code == 400 and "Unknown complaint category" in r.json()["detail"]


async def test_staff_cannot_file_as_citizen(client, make_staff):
    _, h = await make_staff("officer")
    assert (await client.post(API, headers=h, json=BODY)).status_code == 400


async def test_uncategorised_complaint_needs_triage_with_default_sla(client, make_citizen):
    c = await make_citizen()
    out = await _submit(client, c["headers"])
    assert out["status"] == "needs_triage" and out["reference_number"].startswith("MYG-")
    created = datetime.fromisoformat(out["created_at"])
    due = datetime.fromisoformat(out["due_date"])
    assert abs((due - created) - timedelta(hours=72)) < timedelta(minutes=2)


async def test_categorised_complaint_uses_sla_rule_and_priority(client, make_citizen, conn):
    dept = await conn.fetchval("SELECT department_id FROM administration.department ORDER BY 1 LIMIT 1")
    cat = await _make_category(conn, "CAT-T-SLA", dept, "critical", 100)
    await conn.execute("INSERT INTO complaints.sla_rule (department_id, category_id, priority, resolution_hours, "
                       "escalation_hours) VALUES ($1,$2,'critical',10,4)", dept, cat)
    c = await make_citizen()
    out = await _submit(client, c["headers"], category_id=cat)
    assert out["status"] == "classified" and out["department_name"]
    row = await conn.fetchrow("SELECT priority, created_at, due_date, escalation_due_at, department_id, category_confidence "
                              "FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"])
    assert row["priority"] == "critical" and row["department_id"] == dept
    assert abs((row["due_date"] - row["created_at"]) - timedelta(hours=10)) < timedelta(minutes=2)
    assert abs((row["escalation_due_at"] - row["created_at"]) - timedelta(hours=4)) < timedelta(minutes=2)


async def test_category_without_sla_rule_uses_category_default_hours(client, make_citizen, conn):
    dept = await conn.fetchval("SELECT department_id FROM administration.department ORDER BY 1 LIMIT 1")
    cat = await _make_category(conn, "CAT-T-DEF", dept, "low", 36)
    out = await _submit(client, (await make_citizen())["headers"], category_id=cat)
    row = await conn.fetchrow("SELECT created_at, due_date FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"])
    assert abs((row["due_date"] - row["created_at"]) - timedelta(hours=36)) < timedelta(minutes=2)


async def test_routing_prefers_district_authority_then_state(client, make_citizen, conn):
    dept = await conn.fetchval("SELECT department_id FROM administration.department ORDER BY 1 DESC LIMIT 1")
    cat = await _make_category(conn, "CAT-T-ROUTE", dept)
    await conn.execute("INSERT INTO complaints.routing_rule (category_id, jurisdiction_level, department_id, authority_type) "
                       "VALUES ($1,'district',$2,'district')", cat, dept)
    state = await conn.fetchval("INSERT INTO administration.authority (department_id, authority_type, authority_name, "
                                "jurisdiction_level) VALUES ($1,'state','T-State','state') RETURNING authority_id", dept)
    d1 = await conn.fetchval("INSERT INTO administration.authority (department_id, authority_type, authority_name, "
                             "jurisdiction_level, jurisdiction_id) VALUES ($1,'district','T-D1','district',1) RETURNING authority_id", dept)
    d2 = await conn.fetchval("INSERT INTO administration.authority (department_id, authority_type, authority_name, "
                             "jurisdiction_level, jurisdiction_id) VALUES ($1,'district','T-D2','district',2) RETURNING authority_id", dept)
    h = (await make_citizen())["headers"]
    got = {}
    for district in (1, 2, 7):
        out = await _submit(client, h, category_id=cat, district_id=district)
        got[district] = await conn.fetchval("SELECT authority_id FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"])
    assert got == {1: d1, 2: d2, 7: state}
    track = (await client.get(f"{API}/track/{out['reference_number']}")).json()
    assert track["authority_name"] == "T-State"


async def test_supplied_district_survives_when_boundaries_unresolved(client, make_citizen, conn):
    """resolve_jurisdiction yields nothing (no boundary data); the caller's district must be kept."""
    out = await _submit(client, (await make_citizen())["headers"], latitude=13.08, longitude=80.27, district_id=1)
    assert await conn.fetchval("SELECT district_id FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"]) == 1


# -- tracking / listing / access -------------------------------------------------------
async def test_public_tracking_and_anonymous_hidden(client, make_citizen):
    h = (await make_citizen())["headers"]
    pub = await _submit(client, h)
    anon = await _submit(client, h, is_anonymous=True)
    t = await client.get(f"{API}/track/{pub['reference_number']}")
    assert t.status_code == 200 and t.json()["timeline"][0]["new_status"] == "needs_triage"
    assert (await client.get(f"{API}/track/{anon['reference_number']}")).status_code == 404
    assert (await client.get(f"{API}/track/MYG-0000-000000")).status_code == 404


async def test_my_complaints_pagination_and_isolation(client, make_citizen):
    a, b = await make_citizen(), await make_citizen()
    for _ in range(3):
        await _submit(client, a["headers"])
    await _submit(client, b["headers"])
    page = (await client.get(f"{API}/mine", headers=a["headers"], params={"page_size": 2})).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["pages"] == 2
    assert (await client.get(f"{API}/mine", headers=b["headers"])).json()["total"] == 1
    assert (await client.get(f"{API}/mine", headers=a["headers"], params={"status": "resolved"})).json()["total"] == 0
    assert (await client.get(f"{API}/mine")).status_code == 401


async def test_complaint_detail_authorization(client, make_citizen, make_staff, conn):
    owner, other = await make_citizen(), await make_citizen()
    _, officer = await make_staff("officer")
    out = await _submit(client, owner["headers"], address="12 Anna Salai")
    cid = await conn.fetchval("SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"])
    url = f"{API}/{cid}"
    mine = await client.get(url, headers=owner["headers"])
    assert mine.status_code == 200 and mine.json()["address"] == "12 Anna Salai" and mine.json()["timeline"]
    assert (await client.get(url, headers=other["headers"])).status_code == 403   # not someone else's complaint
    assert (await client.get(url, headers=officer)).status_code == 200            # staff may read
    assert (await client.get(url)).status_code == 401
    assert (await client.get(f"{API}/00000000-0000-0000-0000-000000000000", headers=officer)).status_code == 404


# -- status transitions ----------------------------------------------------------------
async def test_status_update_rbac_and_state_machine(client, make_citizen, make_staff, conn):
    owner = await make_citizen()
    uid, officer = await make_staff("officer")
    out = await _submit(client, owner["headers"])
    cid = await conn.fetchval("SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"])
    url = f"{API}/{cid}/status"

    assert (await client.patch(url, headers=owner["headers"], json={"new_status": "classified"})).status_code == 403
    assert (await client.patch(url, json={"new_status": "classified"})).status_code == 401
    assert (await client.patch(url, headers=officer, json={"new_status": "resolved"})).status_code == 409   # illegal jump
    assert (await client.patch(url, headers=officer, json={"new_status": "bogus"})).status_code == 400
    bad = await client.patch(f"{API}/00000000-0000-0000-0000-000000000000/status", headers=officer, json={"new_status": "classified"})
    assert bad.status_code == 404

    for step, note in (("classified", "triaged"), ("assigned", "to JE"), ("in_progress", "work started"), ("resolved", "patched")):
        r = await client.patch(url, headers=officer, json={"new_status": step, "remarks": note})
        assert r.status_code == 200, (step, r.text)

    hist = await conn.fetch("SELECT old_status, new_status, remarks, changed_by FROM complaints.complaint_history "
                            "WHERE complaint_id=$1 ORDER BY history_id", cid)
    assert [h["new_status"] for h in hist] == ["needs_triage", "classified", "assigned", "in_progress", "resolved"]  # no duplicates
    assert hist[-1]["remarks"] == "patched" and hist[-1]["changed_by"] == uid and hist[-1]["old_status"] == "in_progress"
    assert await conn.fetchval("SELECT resolved_at IS NOT NULL FROM complaints.complaint WHERE complaint_id=$1", cid)
    assert (await client.patch(url, headers=officer, json={"new_status": "closed"})).status_code == 200
    assert (await client.patch(url, headers=officer, json={"new_status": "reopened"})).status_code == 409  # closed is terminal


async def test_categories_endpoint_contract(client):
    cats = (await client.get(f"{API}/categories/list")).json()
    assert len(cats) >= 10 and {"category_id", "name", "name_ta", "default_priority"} <= set(cats[0])
    assert isinstance(cats[0]["category_id"], int)


# -- SLA scheduler ---------------------------------------------------------------------
async def test_scheduler_escalates_only_legal_overdue_complaints(client, make_citizen, session_factory, conn):
    h = (await make_citizen())["headers"]
    dept = await conn.fetchval("SELECT department_id FROM administration.department ORDER BY 1 LIMIT 1")
    parent = await conn.fetchval("INSERT INTO administration.authority (department_id, authority_type, authority_name, "
                                 "jurisdiction_level) VALUES ($1,'state','Sched-Parent','state') RETURNING authority_id", dept)
    child = await conn.fetchval("INSERT INTO administration.authority (department_id, authority_type, authority_name, "
                                "jurisdiction_level, jurisdiction_id, parent_authority_id) "
                                "VALUES ($1,'district','Sched-Child','district',1,$2) RETURNING authority_id", dept, parent)
    refs = {}
    for status in ("assigned", "in_progress", "submitted", "resolved"):
        out = await _submit(client, h)
        await conn.execute("UPDATE complaints.complaint SET status=$2, authority_id=$3, "
                           "escalation_due_at = now() - interval '1 hour' WHERE complaint_ref=$1",
                           out["reference_number"], status, child)
        refs[status] = out["reference_number"]
    fresh = await _submit(client, h)  # not overdue
    await conn.execute("UPDATE complaints.complaint SET status='assigned' WHERE complaint_ref=$1", fresh["reference_number"])

    n = await escalate_overdue_complaints(session_factory)
    assert n >= 2
    status = {k: await conn.fetchval("SELECT status FROM complaints.complaint WHERE complaint_ref=$1", v) for k, v in refs.items()}
    assert status == {"assigned": "escalated", "in_progress": "escalated", "submitted": "submitted", "resolved": "resolved"}
    assert await conn.fetchval("SELECT status FROM complaints.complaint WHERE complaint_ref=$1", fresh["reference_number"]) == "assigned"

    cid = await conn.fetchval("SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1", refs["assigned"])
    hist = await conn.fetch("SELECT new_status, remarks FROM complaints.complaint_history WHERE complaint_id=$1 AND new_status='escalated'", cid)
    assert len(hist) == 1 and hist[0]["remarks"] == "Auto-escalated by SLA scheduler"   # one row, not two
    esc = await conn.fetchrow("SELECT from_authority_id, to_authority_id, status FROM complaints.escalation WHERE complaint_id=$1", cid)
    assert (esc["from_authority_id"], esc["to_authority_id"], esc["status"]) == (child, parent, "open")

    assert await escalate_overdue_complaints(session_factory) == 0   # idempotent: nothing left to escalate
