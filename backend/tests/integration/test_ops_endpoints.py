"""Health, admin connection/graph endpoints, logout and the evidence-upload endpoint."""
import pytest

from app.core.config import settings

pytestmark = pytest.mark.db
API = "/api/v1"


@pytest.fixture(autouse=True)
def _no_graph(monkeypatch):
    """Keep health checks fast and deterministic: no Neo4j probe unless a test asks for it."""
    monkeypatch.setattr(settings, "FEATURE_GRAPH", False)


def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_keys(v)


async def test_public_health_when_dependencies_are_down_shows_state_without_internal_error_text(client):
    """The app's own engine targets an unreachable host here, so this IS the 'database down' case."""
    r = await client.get("/health")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "degraded"
    assert body["services"]["postgresql"]["status"] == "unhealthy"
    assert body["services"]["neo4j"]["status"] == "disabled"
    flat = repr(body)
    assert "error" not in set(_all_keys(body)) and "getaddrinfo" not in flat and "postgres" not in flat.replace("'postgresql'", "")


async def test_public_health_reports_healthy_when_all_checks_pass(client, monkeypatch):
    from app.core import health

    async def ok():
        return {"status": "healthy"}

    for name in ("check_postgres", "check_redis", "check_minio"):
        monkeypatch.setattr(health, name, ok)
    body = (await client.get("/health")).json()
    assert body["status"] == "healthy" and all(v["status"] in ("healthy", "disabled") for v in body["services"].values())


async def test_admin_health_requires_admin_and_includes_details(client, make_citizen, make_staff):
    assert (await client.get(f"{API}/admin/health")).status_code == 401
    c = await make_citizen()
    assert (await client.get(f"{API}/admin/health", headers=c["headers"])).status_code == 403
    _, admin = await make_staff("state_admin")
    body = (await client.get(f"{API}/admin/health", headers=admin)).json()
    assert "error" in body["services"]["redis"]                      # operators do get the diagnostic text


@pytest.mark.parametrize("path", ["/admin/databases/connections", "/admin/knowledge-graph/stats"])
async def test_admin_infrastructure_endpoints_are_protected(client, make_citizen, make_staff, path):
    assert (await client.get(f"{API}{path}")).status_code == 401
    assert (await client.get(f"{API}{path}", headers=(await make_citizen())["headers"])).status_code == 403
    _, admin = await make_staff("state_admin")
    r = await client.get(f"{API}{path}", headers=admin)
    assert r.status_code == 200


async def test_graph_stats_report_disabled_feature_honestly(client, make_staff):
    _, admin = await make_staff("state_admin")
    assert (await client.get(f"{API}/admin/knowledge-graph/stats", headers=admin)).json() == {"status": "disabled"}


async def test_graph_stats_unreachable_graph_is_reported_not_crashed(client, make_staff, monkeypatch):
    monkeypatch.setattr(settings, "FEATURE_GRAPH", True)
    monkeypatch.setattr(settings, "NEO4J_URI", "bolt://localhost:1")
    _, admin = await make_staff("state_admin")
    body = (await client.get(f"{API}/admin/knowledge-graph/stats", headers=admin)).json()
    assert body["status"] == "unavailable"


async def test_admin_role_list_matches_database_roles(conn):
    roles = {r[0] for r in await conn.fetch(
        "SELECT unnest(regexp_matches(pg_get_constraintdef(c.oid), '''(\\w+)''', 'g')) FROM pg_constraint c "
        "WHERE c.conrelid = 'identity.app_user'::regclass AND c.contype = 'c' AND pg_get_constraintdef(c.oid) LIKE '%role%'")}
    from app.api.v1.admin import admin_dep

    allowed = next(c.cell_contents for c in admin_dep.__closure__ if isinstance(c.cell_contents, list))
    assert set(allowed) <= roles, f"admin_dep allows roles the database cannot store: {set(allowed) - roles}"


# -- logout ---------------------------------------------------------------------------------------------
async def test_logout_requires_auth_and_is_audited(client, make_citizen, conn):
    assert (await client.post(f"{API}/auth/logout")).status_code == 401
    mark = await conn.fetchval("SELECT coalesce(max(audit_id),0) FROM audit.audit_log")
    c = await make_citizen()
    r = await client.post(f"{API}/auth/logout", headers=c["headers"])
    assert r.status_code == 200
    assert await conn.fetchval("SELECT count(*) FROM audit.audit_log WHERE audit_id>$1 AND action='LOGOUT'", mark) == 1


# -- evidence upload ------------------------------------------------------------------------------------
PNG = ("proof.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")


async def _complaint(client, headers, conn):
    out = (await client.post(f"{API}/complaints", headers=headers, json={"title": "Evidence test", "description": "Complaint that will receive evidence"})).json()
    return await conn.fetchval("SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1", out["reference_number"])


async def test_evidence_upload_is_authorised_validated_and_never_claims_success(client, make_citizen, make_staff, conn):
    owner, other = await make_citizen(), await make_citizen()
    _, officer = await make_staff("officer")
    cid = await _complaint(client, owner["headers"], conn)
    url = f"{API}/complaints/{cid}/evidence"

    assert (await client.post(url, files={"file": PNG})).status_code == 401
    assert (await client.post(url, headers=other["headers"], files={"file": PNG})).status_code == 403          # not their complaint
    assert (await client.post(f"{API}/complaints/00000000-0000-0000-0000-000000000000/evidence", headers=owner["headers"], files={"file": PNG})).status_code == 404
    bad = await client.post(url, headers=owner["headers"], files={"file": ("x.exe", b"MZ", "application/x-msdownload")})
    assert bad.status_code == 415 and "not allowed" in bad.json()["detail"]

    ok_type = await client.post(url, headers=owner["headers"], files={"file": PNG})
    assert ok_type.status_code == 503                                  # storage not configured: honest failure, not a fake 200
    assert "NOT saved" in ok_type.json()["detail"]
    assert (await client.post(url, headers=officer, files={"file": PNG})).status_code == 503                    # staff pass authorisation too
    assert await conn.fetchval("SELECT count(*) FROM complaints.evidence WHERE complaint_id=$1", cid) == 0     # nothing was recorded
