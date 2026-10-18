"""Admin authorization & audit log, AI chat grounding/ownership, documents, verification governance."""
import uuid

import asyncpg
import pytest

from scripts import db_verify, seed

pytestmark = pytest.mark.db
API = "/api/v1"


# -- admin -----------------------------------------------------------------------------
ADMIN_GETS = ["/admin/overview", "/admin/schemas", "/admin/datasets", "/admin/sources",
              "/admin/audit-logs", "/admin/data-quality", "/admin/relationships"]


@pytest.mark.parametrize("path", ADMIN_GETS)
async def test_admin_endpoints_deny_anonymous_and_citizens(client, make_citizen, path):
    assert (await client.get(f"{API}{path}")).status_code == 401
    c = await make_citizen()
    assert (await client.get(f"{API}{path}", headers=c["headers"])).status_code == 403


@pytest.mark.parametrize("role", ["officer", "department_admin"])
async def test_admin_endpoints_deny_non_admin_staff(client, make_staff, role):
    _, h = await make_staff(role)
    assert (await client.get(f"{API}/admin/overview", headers=h)).status_code == 403


@pytest.mark.parametrize("path", ADMIN_GETS)
async def test_admin_endpoints_work_for_state_admin(client, make_staff, path):
    _, h = await make_staff("state_admin")
    r = await client.get(f"{API}{path}", headers=h)
    assert r.status_code == 200, r.text


async def test_overview_metrics_are_live_counts_excluding_synthetic(client, make_staff, conn):
    _, h = await make_staff("state_admin")
    body = (await client.get(f"{API}/admin/overview", headers=h)).json()
    st = body["database_stats"]
    assert st["schemes"] == 12 and st["services"] == 10 and st["districts"] == 38 and st["departments"] == 17
    assert st["complaints_total"] == await conn.fetchval("SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic")
    assert st["complaints_unassigned"] == await conn.fetchval(
        "SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic AND authority_id IS NULL AND status NOT IN ('resolved','closed','rejected')")
    assert body["verification"]["schemes"].get("official_verified", 0) == 0
    assert sum(body["verification"]["districts"].values()) == 38


async def test_audit_log_retrieval_uses_real_columns(client, make_staff, conn):
    uid, h = await make_staff("state_admin")
    await conn.execute("INSERT INTO audit.audit_log (user_id, user_role, action, entity_type, entity_id, ip_address) "
                       "VALUES ($1,'state_admin','TEST_ACTION','scheme','S-1','10.0.0.1')", uid)
    r = await client.get(f"{API}/admin/audit-logs", headers=h, params={"limit": 5})
    body = r.json()
    assert r.status_code == 200 and "error" not in body, body
    row = next(x for x in body["rows"] if x["action"] == "TEST_ACTION")
    assert {"log_id", "actor_id", "actor_role", "created_at", "entity_type", "entity_id"} <= set(row)
    assert row["actor_id"] == str(uid) and row["actor_role"] == "state_admin"
    assert (await client.get(f"{API}/admin/audit-logs", headers=h, params={"limit": 0})).status_code == 422


async def test_audit_log_is_append_only(conn):
    await conn.execute("INSERT INTO audit.audit_log (action, entity_type) VALUES ('IMMUTABLE','x')")
    for stmt in ("UPDATE audit.audit_log SET action='tampered'", "DELETE FROM audit.audit_log"):
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(stmt)


async def test_admin_table_sample_redacts_credentials(client, make_staff):
    _, h = await make_staff("state_admin")
    r = (await client.get(f"{API}/admin/schemas/identity/tables/app_user/sample", headers=h)).json()
    assert r["rows"], r
    assert all(row["password_hash"] == "[REDACTED]" for row in r["rows"])


async def test_admin_table_sample_rejects_injection_and_unknowns(client, make_staff):
    _, h = await make_staff("state_admin")
    inj = await client.get(f'{API}/admin/schemas/identity/tables/app_user";select/sample', headers=h)
    assert inj.status_code in (404, 422) or "error" in inj.json()
    assert "error" in (await client.get(f"{API}/admin/schemas/pg_catalog/tables/pg_user/sample", headers=h)).json()
    assert "error" in (await client.get(f"{API}/admin/schemas/identity/tables/nope_table/sample", headers=h)).json()


async def test_sql_workspace_is_system_admin_only_and_read_only(client, make_staff, conn):
    _, state = await make_staff("state_admin")
    _, sysadm = await make_staff("system_admin")
    q = {"sql": "SELECT count(*) AS n FROM administration.district"}
    assert (await client.post(f"{API}/admin/query", headers=state, json=q)).status_code == 403
    ok = (await client.post(f"{API}/admin/query", headers=sysadm, json=q)).json()
    assert ok["rows"][0]["n"] == 38
    for bad in ("DELETE FROM administration.district", "SELECT password_hash FROM identity.app_user",
                "SELECT nextval('complaints.complaint_seq')", "SELECT 1; SELECT 2"):
        out = (await client.post(f"{API}/admin/query", headers=sysadm, json={"sql": bad})).json()
        assert "error" in out, bad
    assert await conn.fetchval("SELECT count(*) FROM administration.district") == 38


# -- chat ------------------------------------------------------------------------------
async def test_chat_cites_sources_and_flags_unverified(client):
    r = await client.post(f"{API}/chat/message", json={"message": "Tell me about the breakfast scheme for school children"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["citations"] and not b["abstained"]
    assert all(c["verification_status"] in ("provisional", "externally_referenced") for c in b["citations"])
    assert b["contains_unverified"] is True
    assert "NOT been confirmed" in b["answer"] and "verified against official sources" not in b["answer"]
    assert any("Breakfast" in c["title"] for c in b["citations"])
    assert b["trust_score"] < 0.7   # below TRUST_THRESHOLD: provisional sources never earn high trust


async def test_chat_abstains_without_supporting_sources(client):
    b = (await client.post(f"{API}/chat/message", json={"message": "zzqqxx vvwwyy"})).json()
    assert b["abstained"] is True and b["abstain_reason"] == "no_supporting_sources" and b["citations"] == []
    assert b["trust_score"] == 0.0 and "tn.gov.in" in b["answer"]


async def test_chat_validates_input(client):
    assert (await client.post(f"{API}/chat/message", json={})).status_code == 422


async def test_chat_lineage_and_conversation_ownership(client, make_citizen, conn):
    a, b = await make_citizen(), await make_citizen()
    r = (await client.post(f"{API}/chat/message", headers=a["headers"],
                           json={"message": "pension scheme for old age"})).json()
    conv, dec = r["conversation_id"], r["decision_id"]

    msgs = await client.get(f"{API}/chat/conversations/{conv}", headers=a["headers"])
    assert msgs.status_code == 200 and [m["role"] for m in msgs.json()] == ["user", "assistant"]
    assert (await client.get(f"{API}/chat/conversations/{conv}", headers=b["headers"])).status_code == 404   # not theirs
    assert (await client.get(f"{API}/chat/conversations/{conv}")).status_code == 404                        # anonymous

    mine = (await client.get(f"{API}/chat/conversations", headers=a["headers"])).json()
    assert [c["conversation_id"] for c in mine] == [conv] and mine[0]["message_count"] == 2
    assert (await client.get(f"{API}/chat/conversations", headers=b["headers"])).json() == []

    lin = await client.get(f"{API}/chat/decisions/{dec}/lineage", headers=a["headers"])
    assert lin.status_code == 200
    srcs = lin.json()["sources"]
    assert len(srcs) == len(r["citations"]) and all("verification_status=" in s["reason"] for s in srcs)
    assert (await client.get(f"{API}/chat/decisions/{dec}/lineage", headers=b["headers"])).status_code == 404
    assert (await client.get(f"{API}/chat/decisions/{dec}/lineage")).status_code == 404


async def test_anonymous_chat_decision_is_traceable(client):
    r = (await client.post(f"{API}/chat/message", json={"message": "breakfast scheme"})).json()
    lin = await client.get(f"{API}/chat/decisions/{r['decision_id']}/lineage")
    assert lin.status_code == 200 and lin.json()["decision_type"] == "information_answer"


# -- documents -------------------------------------------------------------------------
async def test_documents_list_and_search(client, conn):
    assert (await client.get(f"{API}/documents")).json()["total"] >= 0
    did = await conn.fetchval(
        "INSERT INTO documents.document (title, document_type, full_text, file_hash, source_url, status) "
        "VALUES ('Test GO on widgets','GO','This order concerns widget subsidies.', $1, 'https://example.com/go', 'active') "
        "RETURNING document_id", uuid.uuid4().hex)
    await conn.execute("UPDATE documents.document SET extraction_status='ok' WHERE document_id=$1", did)
    await conn.execute("INSERT INTO documents.document_chunk (document_id,chunk_number,content,page_number) VALUES ($1,0,'This order concerns widget subsidies.',1)", did)
    lst = (await client.get(f"{API}/documents", params={"q": "widget"})).json()
    assert lst["total"] == 1 and lst["items"][0]["doc_type"] == "GO" and lst["items"][0]["verified_at"] is None
    det = (await client.get(f"{API}/documents/{did}")).json()
    assert det["extracted_text"].startswith("This order") and det["chunk_count"] == 1
    hits = (await client.get(f"{API}/documents/search/full-text", params={"q": "widget subsidies"})).json()
    assert hits and hits[0]["title"] == "Test GO on widgets"
    chat = (await client.post(f"{API}/chat/message", json={"message": "widget subsidies order policy"})).json()
    doc_cits = [c for c in chat["citations"] if c["title"] == "Test GO on widgets"]
    assert doc_cits and doc_cits[0]["verification_status"] == "unverified"   # ingested docs are not verified by default
    assert doc_cits[0]["chunk_id"] and doc_cits[0]["page"] == 1 and doc_cits[0]["document_id"] == str(did)


# -- verification governance (DB level) ------------------------------------------------
async def test_db_rejects_verified_without_document_reference(conn):
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute("UPDATE administration.department SET verification_status='official_verified' WHERE department_code='REVT'")
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute("UPDATE administration.district SET verification_status='official_verified' WHERE district_code='TN-CHN'")
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute("UPDATE services.service SET verification_status='official_verified', source_document_ref='  ' "
                           "WHERE service_code='SVC-NATIVITY'")


async def test_promotion_with_reference_is_logged_with_reason(conn):
    try:
        await _promotion_body(conn)
    except _Rollback:
        pass


async def _promotion_body(conn):
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.verification_reason','test promotion with evidence',true)")
        await conn.execute("UPDATE administration.district SET verification_status='official_verified', "
                           "source_document_ref='TEST-REF-1' WHERE district_code='TN-CBE'")
        log = await conn.fetchrow("SELECT * FROM system.verification_status_log WHERE record_key='TN-CBE' "
                                  "ORDER BY log_id DESC LIMIT 1")
        assert (log["old_status"], log["new_status"], log["reason"]) == ("provisional", "official_verified", "test promotion with evidence")
        assert log["changed_at"] is not None and log["table_name"] == "administration.district"
        await conn.execute("SELECT set_config('app.verification_reason','test demotion',true)")
        await conn.execute("UPDATE administration.district SET verification_status='provisional', source_document_ref=NULL "
                           "WHERE district_code='TN-CBE'")
        demo = await conn.fetchrow("SELECT old_status, new_status FROM system.verification_status_log "
                                   "WHERE record_key='TN-CBE' ORDER BY log_id DESC LIMIT 1")
        assert (demo["old_status"], demo["new_status"]) == ("official_verified", "provisional")
        raise _Rollback


class _Rollback(Exception):
    pass


async def test_deprecated_is_terminal(conn):
    try:
        async with conn.transaction():
            await conn.execute("UPDATE schemes.scheme SET verification_status='deprecated' WHERE scheme_code='TN-PM-KISAN'")
            with pytest.raises(asyncpg.PostgresError, match="deprecated"):
                await conn.execute("UPDATE schemes.scheme SET verification_status='provisional' WHERE scheme_code='TN-PM-KISAN'")
            raise _Rollback
    except _Rollback:
        pass


async def test_new_rows_default_to_provisional(conn):
    async with conn.transaction():
        await conn.execute("INSERT INTO administration.department (department_code, department_name) VALUES ('ZZ-T','Test dept')")
        assert await conn.fetchval("SELECT verification_status FROM administration.department WHERE department_code='ZZ-T'") == "provisional"
        await conn.execute("DELETE FROM system.verification_status_log WHERE record_key='ZZ-T'")
        await conn.execute("DELETE FROM administration.department WHERE department_code='ZZ-T'")


async def test_status_log_holds_seed_history(conn):
    n = await conn.fetchval("SELECT count(*) FROM system.verification_status_log WHERE new_status='provisional'")
    assert n >= 80
    assert await conn.fetchval("SELECT count(*) FROM system.verification_status_log WHERE reason = 'no reason supplied'") == 0


async def test_upgrade_path_demotes_and_logs_previous_official_verified(admin_dsn, has_postgis):
    """An existing database that carries the earlier unsupported classification is demoted by the seed."""
    name = f"mygovt_test_up_{uuid.uuid4().hex[:6]}"
    admin = await asyncpg.connect(admin_dsn)
    await admin.execute(f'CREATE DATABASE "{name}"')
    try:
        c = await asyncpg.connect(db_verify.with_db(admin_dsn, name))
        try:
            sql = db_verify.SCHEMA.read_text(encoding="utf-8")
            if not has_postgis:
                await c.execute(db_verify.POSTGIS_STUBS)
                sql = db_verify.strip_postgis(sql)
            await c.execute(sql)
            for m in db_verify.MIGRATIONS[:2]:             # 002, 003 only: the pre-governance state
                await c.execute(m.read_text(encoding="utf-8"))
            await c.execute("INSERT INTO administration.state (state_code, state_name) VALUES ('TN','Tamil Nadu')")
            await c.execute("INSERT INTO administration.district (district_id, state_id, district_code, district_name) VALUES (900,1,'TN-OLD','Old')")
            await c.execute("INSERT INTO administration.department (department_id, department_code, department_name, verification_status) "
                            "VALUES (900,'OLD','Old dept','official_verified')")
            await c.execute("INSERT INTO schemes.scheme (scheme_code, scheme_name, scheme_level, verification_status) "
                            "VALUES ('OLD-S','Old scheme','state','official_verified')")
            for m in db_verify.MIGRATIONS[2:]:             # 004: structure only, constraints NOT VALID
                if not has_postgis and "postgis" in m.name:
                    continue
                await c.execute(m.read_text(encoding="utf-8"))
            # old rows still claim verification and the constraint does not (yet) police them
            assert await c.fetchval("SELECT count(*) FROM schemes.scheme WHERE verification_status='official_verified'") == 1
            await seed.apply_seed(c)
            assert await c.fetchval("SELECT count(*) FROM schemes.scheme WHERE verification_status='official_verified'") == 0
            assert await c.fetchval("SELECT count(*) FROM administration.department WHERE verification_status='official_verified'") == 0
            row = await c.fetchrow("SELECT old_status, new_status, reason FROM system.verification_status_log "
                                   "WHERE record_key='OLD-S' ORDER BY log_id DESC LIMIT 1")
            assert (row["old_status"], row["new_status"]) == ("official_verified", "provisional")
            assert "baseline evidence review" in row["reason"]
            failed = {c_.name for c_ in await seed.run_checks(c) if c_.status == "FAIL"}
            # Only checks that the deliberately-added legacy rows (no LGD code / source) can trip may
            # fail; every governance check (constraints validated, no unsupported verified rows,
            # no stale verified_at/by, log written) must pass.
            assert failed <= {"districts == 38", "schemes == 12 (validated JSON)",
                              "all districts have a unique lgd_code", "every scheme has a source_id"}, failed
        finally:
            await c.close()
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()
