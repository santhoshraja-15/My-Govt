"""Complaint routing: seeded routing targets, assignment-state reporting, missing/ambiguous mappings."""
import pytest

from app.services.complaint_rules import assignment_state

pytestmark = pytest.mark.db
API = "/api/v1/complaints"
BODY = {"title": "Water not supplied", "description": "No drinking water supply for three days now"}


@pytest.mark.parametrize("args,expected", [
    ((5, False, 2), "authority_assigned"), ((5, True, 2), "department_level"),
    ((None, False, 2), "department_only"), ((None, False, None), "unassigned"),
])
def test_assignment_state_rule(args, expected):
    assert assignment_state(*args) == expected


async def test_seed_creates_placeholder_authority_per_department(conn):
    rows = await conn.fetch("SELECT * FROM administration.authority WHERE is_routing_placeholder AND department_id <= 17")
    assert len(rows) == 17   # one per seeded department
    assert {r["verification_status"] for r in rows} == {"provisional"}
    assert all(r["jurisdiction_level"] == "state" and r["parent_authority_id"] is None for r in rows)
    # nothing invented: no officers were created
    assert await conn.fetchval("SELECT count(*) FROM administration.officer") == 0


async def test_every_category_has_a_routing_rule(conn):
    assert await conn.fetchval(
        "SELECT count(*) FROM complaints.complaint_category c WHERE c.category_id <= 10 AND c.default_department_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM complaints.routing_rule r WHERE r.category_id=c.category_id)") == 0
    rule = await conn.fetchrow("SELECT r.department_id, c.default_department_id FROM complaints.routing_rule r "
                               "JOIN complaints.complaint_category c USING (category_id) LIMIT 1")
    assert rule["department_id"] == rule["default_department_id"]


async def test_seed_is_repeatable_for_routing(conn):
    from scripts import seed

    async def snapshot():
        return (await conn.fetchval("SELECT count(*) FROM administration.authority"),
                await conn.fetchval("SELECT count(*) FROM complaints.routing_rule"))

    before = await snapshot()
    await seed.apply_seed(conn)
    assert await snapshot() == before          # repeatable
    # records created later (not defined by the seed) must NOT receive routing rows from a re-seed
    await conn.execute("INSERT INTO administration.department (department_code, department_name) VALUES ('LATE','Late dept')")
    await conn.execute("INSERT INTO complaints.complaint_category (category_code, category_name, default_department_id) "
                       "VALUES ('CAT-LATE','x',(SELECT department_id FROM administration.department WHERE department_code='LATE'))")
    before = await snapshot()
    await seed.apply_seed(conn)
    assert await snapshot() == before


async def test_seeded_category_routes_to_department_level_target(client, make_citizen, conn):
    cat = await conn.fetchrow("SELECT category_id, default_department_id FROM complaints.complaint_category "
                              "WHERE category_code='CAT-WAT'")
    h = (await make_citizen())["headers"]
    out = (await client.post(API, headers=h, json={**BODY, "category_id": cat["category_id"]})).json()
    assert out["assignment_state"] == "department_level" and out["department_name"]
    row = await conn.fetchrow("SELECT department_id, authority_id FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"])
    assert row["department_id"] == cat["default_department_id"] and row["authority_id"] is not None
    assert await conn.fetchval("SELECT is_routing_placeholder FROM administration.authority WHERE authority_id=$1", row["authority_id"])
    track = (await client.get(f"{API}/track/{out['reference_number']}")).json()
    assert track["assignment_state"] == "department_level"
    mine = (await client.get(f"{API}/mine", headers=h)).json()["items"][0]
    assert mine["assignment_state"] == "department_level"


async def test_uncategorised_complaint_is_reported_unassigned(client, make_citizen):
    h = (await make_citizen())["headers"]
    out = (await client.post(API, headers=h, json=BODY)).json()
    assert out["assignment_state"] == "unassigned" and out["status"] == "needs_triage"
    assert (await client.get(f"{API}/track/{out['reference_number']}")).json()["assignment_state"] == "unassigned"


async def test_department_without_any_authority_is_reported_department_only(client, make_citizen, conn):
    dept = await conn.fetchval("INSERT INTO administration.department (department_code, department_name) VALUES ('NOAUTH','No-authority dept') RETURNING department_id")
    cat = await conn.fetchval("INSERT INTO complaints.complaint_category (category_code, category_name, default_department_id) VALUES ('CAT-NOAUTH','x',$1) RETURNING category_id", dept)
    h = (await make_citizen())["headers"]
    out = (await client.post(API, headers=h, json={**BODY, "category_id": cat})).json()
    assert out["assignment_state"] == "department_only" and out["department_name"] == "No-authority dept"
    assert await conn.fetchval("SELECT authority_id FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"]) is None


async def test_specific_authority_beats_placeholder(client, make_citizen, conn):
    dept = await conn.fetchval("SELECT default_department_id FROM complaints.complaint_category WHERE category_code='CAT-ROA'")
    real = await conn.fetchval("INSERT INTO administration.authority (department_id, authority_type, authority_name, jurisdiction_level, jurisdiction_id) "
                               "VALUES ($1,'district','Test District Office','district',4) RETURNING authority_id", dept)
    cat = await conn.fetchval("SELECT category_id FROM complaints.complaint_category WHERE category_code='CAT-ROA'")
    h = (await make_citizen())["headers"]
    in_district = (await client.post(API, headers=h, json={**BODY, "category_id": cat, "district_id": 4})).json()
    elsewhere = (await client.post(API, headers=h, json={**BODY, "category_id": cat, "district_id": 5})).json()
    assert in_district["assignment_state"] == "authority_assigned"
    assert await conn.fetchval("SELECT authority_id FROM complaints.complaint WHERE complaint_ref=$1", in_district["reference_number"]) == real
    assert elsewhere["assignment_state"] == "department_level"     # other district falls back to the department target


async def test_ambiguous_rules_are_resolved_deterministically(client, make_citizen, conn):
    """Two rules for one category: lowest priority_order wins; result is stable across calls."""
    a = await conn.fetchval("INSERT INTO administration.department (department_code, department_name) VALUES ('AMB-A','Amb A') RETURNING department_id")
    b = await conn.fetchval("INSERT INTO administration.department (department_code, department_name) VALUES ('AMB-B','Amb B') RETURNING department_id")
    cat = await conn.fetchval("INSERT INTO complaints.complaint_category (category_code, category_name) VALUES ('CAT-AMB','x') RETURNING category_id")
    await conn.execute("INSERT INTO complaints.routing_rule (category_id, jurisdiction_level, department_id, authority_type, priority_order) VALUES ($1,'state',$2,'x',2), ($1,'district',$3,'x',1)", cat, a, b)
    h = (await make_citizen())["headers"]
    for _ in range(3):
        out = (await client.post(API, headers=h, json={**BODY, "category_id": cat})).json()
        assert out["department_name"] == "Amb B"


async def test_detail_exposes_assignment_state(client, make_citizen, conn):
    cat = await conn.fetchval("SELECT category_id FROM complaints.complaint_category WHERE category_code='CAT-GAR'")
    c = await make_citizen()
    out = (await client.post(API, headers=c["headers"], json={**BODY, "category_id": cat})).json()
    d = (await client.get(f"{API}/{out['complaint_id']}", headers=c["headers"])).json()
    assert d["assignment_state"] == "department_level"
