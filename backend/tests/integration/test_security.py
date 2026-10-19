"""Security behaviour: audit trail, lockout, rate limiting, headers, size limits, data-leak checks."""
import pytest

from app.security.ratelimit import SlidingWindowLimiter
from app.services import audit
from tests.integration.conftest import PASSWORD

pytestmark = pytest.mark.db
API = "/api/v1"


# -- pure limiter ------------------------------------------------------------------------------
def test_sliding_window_limiter():
    t = [0.0]
    lim = SlidingWindowLimiter(limit=3, window_seconds=10, clock=lambda: t[0])
    assert [lim.check("a")[0] for _ in range(3)] == [True, True, True]
    ok, retry = lim.check("a")
    assert not ok and 0 < retry <= 10
    assert lim.check("b")[0]                      # separate key
    t[0] = 10.1
    assert lim.check("a")[0]                      # window slid


def test_pseudonymise_is_stable_and_not_reversible_looking():
    p = audit.pseudonymise("Person@Example.com ")
    assert p == audit.pseudonymise("person@example.com") and "example" not in p and p.startswith("h:")


# -- rate limiting / lockout --------------------------------------------------------------------
async def test_login_is_rate_limited(client):
    codes = [(await client.post(f"{API}/auth/login", json={"email": "x@example.com", "password": "bad-password"})).status_code
             for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
    r = await client.post(f"{API}/auth/login", json={"email": "x@example.com", "password": "bad-password"})
    assert "Retry-After" in r.headers


async def test_registration_is_rate_limited(client):
    codes = [(await client.post(f"{API}/auth/register", json={"email": f"rl{i}@example.com", "password": PASSWORD, "full_name": "R"})).status_code
             for i in range(7)]
    assert codes == [201] * 5 + [429] * 2


async def test_account_locks_after_repeated_failures_without_leaking_state(client, make_citizen, conn):
    c = await make_citizen()
    from app.security import ratelimit
    for _ in range(5):
        assert (await client.post(f"{API}/auth/login", json={"email": c["email"], "password": "wrong-password"})).status_code == 401
        ratelimit.login_limiter.reset()
    # correct password is now refused too (locked) - with the same generic response
    locked = await client.post(f"{API}/auth/login", json={"email": c["email"], "password": PASSWORD})
    assert locked.status_code == 401 and locked.json()["detail"] == "Invalid credentials"
    assert await conn.fetchval("SELECT failed_logins FROM identity.app_user WHERE email=$1", c["email"]) == 5   # no increment while locked
    # lock lapses after the quiet period
    await conn.execute("ALTER TABLE identity.app_user DISABLE TRIGGER trg_app_user_touch")
    await conn.execute("UPDATE identity.app_user SET updated_at = now() - interval '16 minutes' WHERE email=$1", c["email"])
    await conn.execute("ALTER TABLE identity.app_user ENABLE TRIGGER trg_app_user_touch")
    ratelimit.login_limiter.reset()
    assert (await client.post(f"{API}/auth/login", json={"email": c["email"], "password": PASSWORD})).status_code == 200


# -- audit trail --------------------------------------------------------------------------------
async def _events(conn, action, since_id):
    return await conn.fetch("SELECT * FROM audit.audit_log WHERE action=$1 AND audit_id>$2 ORDER BY audit_id", action, since_id)


async def test_sensitive_actions_are_audited_without_secrets(client, make_citizen, make_staff, conn):
    mark = await conn.fetchval("SELECT coalesce(max(audit_id),0) FROM audit.audit_log")
    c = await make_citizen("Audit Person")
    await client.post(f"{API}/auth/login", json={"email": c["email"], "password": "wrong-password"})

    comp = (await client.post(f"{API}/complaints", headers=c["headers"],
                              json={"title": "Audit me", "description": "A complaint to check the audit trail"})).json()
    _, officer = await make_staff("officer")
    cid = await conn.fetchval("SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1", comp["reference_number"])
    await client.patch(f"{API}/complaints/{cid}/status", headers=officer, json={"new_status": "classified", "remarks": "ok"})
    await client.patch(f"{API}/complaints/{cid}/status", headers=officer, json={"new_status": "closed"})   # illegal -> failure event
    await client.put(f"{API}/citizens/profile", headers=c["headers"],
                     json={"gender": "female", "annual_income": 123456, "profile_consent": True})

    rows = await conn.fetch("SELECT action, user_role, entity_id, new_value::text AS nv, ip_address, request_id "
                            "FROM audit.audit_log WHERE audit_id>$1 ORDER BY audit_id", mark)
    actions = [r["action"] for r in rows]
    for expected in ("USER_REGISTERED", "LOGIN_SUCCESS", "LOGIN_FAILED", "COMPLAINT_SUBMITTED",
                     "COMPLAINT_STATUS_CHANGED", "COMPLAINT_STATUS_REJECTED", "PROFILE_UPDATED"):
        assert expected in actions, (expected, actions)

    blob = " ".join((r["nv"] or "") + (r["entity_id"] or "") for r in rows)
    assert PASSWORD not in blob and "wrong-password" not in blob           # no credentials
    assert c["email"] not in blob and "Audit Person" not in blob            # no e-mail / name
    assert "123456" not in blob                                             # no profile VALUES, only field names
    prof = next(r for r in rows if r["action"] == "PROFILE_UPDATED")
    assert '"fields_set"' in prof["nv"] and "annual_income" in prof["nv"] and prof["user_role"] == "citizen"
    failed = next(r for r in rows if r["action"] == "LOGIN_FAILED")
    assert failed["entity_id"].startswith("h:") and '"outcome": "failure"' in failed["nv"]
    assert all(r["request_id"] for r in rows if r["action"] in ("USER_REGISTERED", "COMPLAINT_SUBMITTED"))
    reject = next(r for r in rows if r["action"] == "COMPLAINT_STATUS_REJECTED")
    assert reject["user_role"] == "officer" and '"outcome": "failure"' in reject["nv"]


async def test_admin_sql_and_table_reads_are_audited(client, make_staff, conn):
    mark = await conn.fetchval("SELECT coalesce(max(audit_id),0) FROM audit.audit_log")
    _, sysadm = await make_staff("system_admin")
    await client.post(f"{API}/admin/query", headers=sysadm, json={"sql": "SELECT 1 AS one"})
    await client.post(f"{API}/admin/query", headers=sysadm, json={"sql": "DELETE FROM x"})
    await client.get(f"{API}/admin/schemas/schemes/tables/scheme/sample", headers=sysadm)
    rows = await conn.fetch("SELECT action, new_value::text nv FROM audit.audit_log WHERE audit_id>$1 ORDER BY audit_id", mark)
    assert [r["action"] for r in rows] == ["ADMIN_SQL_QUERY", "ADMIN_SQL_QUERY", "ADMIN_TABLE_SAMPLE"]
    assert '"rejected": true' in rows[1]["nv"] and '"rejected": false' in rows[0]["nv"]


async def test_scheduler_escalation_is_audited(client, make_citizen, session_factory, conn):
    from app.jobs.scheduler import escalate_overdue_complaints

    mark = await conn.fetchval("SELECT coalesce(max(audit_id),0) FROM audit.audit_log")
    c = await make_citizen()
    comp = (await client.post(f"{API}/complaints", headers=c["headers"], json={"title": "Esc audit", "description": "needs escalation audit"})).json()
    await conn.execute("UPDATE complaints.complaint SET status='assigned', escalation_due_at=now()-interval '1 hour' WHERE complaint_ref=$1", comp["reference_number"])
    await escalate_overdue_complaints(session_factory)
    cid = str(await conn.fetchval("SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1", comp["reference_number"]))
    ev = [r for r in await _events(conn, "COMPLAINT_ESCALATED", mark) if r["entity_id"] == cid]
    assert len(ev) == 1 and ev[0]["user_role"] == "anonymous"


# -- headers / limits / information leakage -----------------------------------------------------
async def test_security_headers_present(client):
    r = await client.get(f"{API}/departments")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in r.headers and r.headers["X-Request-ID"]
    assert (await client.post(f"{API}/auth/login", json={"email": "a@example.com", "password": "x"})).headers["Cache-Control"] == "no-store"


async def test_oversized_body_rejected_before_processing(client):
    big = "x" * (1024 * 1024 + 10)
    r = await client.post(f"{API}/chat/message", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_error_responses_do_not_leak_internals(client):
    for path, kw in ((f"{API}/schemes/not-a-uuid", {}), (f"{API}/complaints/track/%27%3B--", {}),
                     (f"{API}/gis/districts/abc/taluks", {})):
        r = await client.get(path, **kw)
        text = r.text.lower()
        assert r.status_code in (404, 422)
        assert "traceback" not in text and "select " not in text and "asyncpg" not in text and "postgres" not in text


async def test_sql_injection_attempts_are_inert(client, conn):
    n = await conn.fetchval("SELECT count(*) FROM schemes.scheme")
    for q in ("'; DROP TABLE schemes.scheme; --", "\" OR 1=1 --", "%' UNION SELECT password_hash FROM identity.app_user --"):
        r = await client.get(f"{API}/schemes", params={"q": q})
        assert r.status_code == 200 and "password" not in r.text.lower()
        assert (await client.get(f"{API}/documents/search/full-text", params={"q": q})).status_code == 200
        assert (await client.post(f"{API}/chat/message", json={"message": q})).status_code == 200
    assert await conn.fetchval("SELECT count(*) FROM schemes.scheme") == n


async def test_cross_citizen_access_is_blocked_everywhere(client, make_citizen, conn):
    a, b = await make_citizen(), await make_citizen()
    comp = (await client.post(f"{API}/complaints", headers=a["headers"], json={"title": "Private matter", "description": "Details only the owner should see"})).json()
    cid = await conn.fetchval("SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1", comp["reference_number"])
    assert (await client.get(f"{API}/complaints/{cid}", headers=b["headers"])).status_code == 403
    assert comp["reference_number"] not in (await client.get(f"{API}/complaints/mine", headers=b["headers"])).text
    msg = (await client.post(f"{API}/chat/message", headers=a["headers"], json={"message": "pension scheme"})).json()
    assert (await client.get(f"{API}/chat/conversations/{msg['conversation_id']}", headers=b["headers"])).status_code == 404
    # B's profile endpoint only ever returns B's own record
    assert (await client.get(f"{API}/citizens/profile", headers=b["headers"])).json()["citizen_id"] == b["user"]["citizen_id"]


async def test_docs_hidden_in_production(monkeypatch):
    from app.core.config import Settings

    prod = Settings(APP_ENV="production", JWT_SECRET_KEY="x" * 48, POSTGRES_PASSWORD="strong-db-password",
                    NEO4J_PASSWORD="strong-neo4j-pw", MINIO_SECRET_KEY="strong-minio-secret")
    assert prod.APP_ENV == "production"      # the main module reads settings.APP_ENV at import time
    import app.main

    with open(app.main.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert 'docs_url=None if settings.APP_ENV.lower() == "production"' in src
