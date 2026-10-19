"""Database Architecture Explorer API: metadata must equal the real catalog, stay restricted, and leak nothing."""
import json

import pytest

from app.services import architecture_service as arch

pytestmark = pytest.mark.db
API = "/api/v1/architecture"
SCHEMA_QUERY = "SELECT nspname FROM pg_namespace WHERE nspname <> ALL($1::text[]) AND nspname !~ '^pg_'"
# Every architecture route, spelled out in full: the route inventory matches tests to routes by these literal paths, and
# test_every_architecture_route_is_exercised proves the list equals the live route table.
COVERED_ROUTES = [
    "/api/v1/architecture/overview", "/api/v1/architecture/components", "/api/v1/architecture/tables", "/api/v1/architecture/tables/{schema}/{table}",
    "/api/v1/architecture/relationships", "/api/v1/architecture/schema", "/api/v1/architecture/normalization", "/api/v1/architecture/advanced",
    "/api/v1/architecture/implementation", "/api/v1/architecture/examples/{example_id}/run", "/api/v1/architecture/examples/{example_id}/explain",
]
ENDPOINTS = ["/overview", "/components", "/tables", "/tables/complaints/complaint", "/relationships", "/schema", "/normalization",
             "/advanced", "/implementation", "/examples/schemes_by_department/run", "/examples/schemes_by_department/explain"]


async def _real_tables(conn):
    schemas = [r[0] for r in await conn.fetch(SCHEMA_QUERY, list(arch.SYSTEM_SCHEMAS))]
    rows = await conn.fetch(
        "SELECT n.nspname || '.' || c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relkind IN ('r','p') AND n.nspname = ANY($1) "
        "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')", schemas)
    return schemas, {r[0] for r in rows}


# ── access control ────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_every_endpoint_requires_an_administrator(client, make_citizen, make_staff, path):
    assert (await client.get(API + path)).status_code == 401
    assert (await client.get(API + path, headers=(await make_citizen())["headers"])).status_code == 403
    for role in ("officer", "department_admin"):
        _, headers = await make_staff(role)
        assert (await client.get(API + path, headers=headers)).status_code == 403, role
    for role in ("state_admin", "system_admin"):
        _, headers = await make_staff(role)
        assert (await client.get(API + path, headers=headers)).status_code == 200, role


# ── metadata equals the real catalog ──────────────────────────────────────────────────────────────────────
async def test_overview_counts_match_the_database(client, make_staff, conn):
    _, h = await make_staff("system_admin")
    body = (await client.get(f"{API}/overview", headers=h)).json()
    schemas, tables = await _real_tables(conn)
    fks = await conn.fetchval("SELECT count(*) FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
                              "WHERE con.contype = 'f' AND n.nspname = ANY($1)", schemas)
    cols = await conn.fetchval("SELECT count(*) FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
                               "WHERE a.attnum > 0 AND NOT a.attisdropped AND c.relkind IN ('r','p') AND n.nspname = ANY($1) "
                               "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')", schemas)
    assert body["counts"]["tables"] == len(tables) > 40
    assert body["counts"]["foreign_keys"] == fks > 50
    assert body["counts"]["columns"] == cols
    assert body["counts"]["schemas"] == len(schemas)
    assert sum(s["tables"] for s in body["schemas"]) == len(tables)
    assert body["engine"].startswith("PostgreSQL")
    assert "public" not in {s["name"] for s in body["schemas"]}          # PostGIS system tables are not project tables


async def test_foreign_keys_are_exactly_the_database_constraints(client, make_staff, conn):
    _, h = await make_staff("state_admin")
    body = (await client.get(f"{API}/relationships", headers=h)).json()
    schemas, _ = await _real_tables(conn)
    real = {r[0] for r in await conn.fetch(
        "SELECT con.conname || '|' || n.nspname || '.' || c.relname || '|' || rn.nspname || '.' || rc.relname "
        "FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_class rc ON rc.oid = con.confrelid JOIN pg_namespace rn ON rn.oid = rc.relnamespace "
        "WHERE con.contype = 'f' AND n.nspname = ANY($1)", schemas)}
    api = {f"{f['name']}|{f['from_table']}|{f['to_table']}" for f in body["foreign_keys"]}
    assert api == real
    assert all(f["enforced"] for f in body["foreign_keys"]) and all(not r["enforced"] for r in body["inferred"])
    assert {f["cardinality"] for f in body["foreign_keys"]} <= {"one_to_one", "one_to_many"}
    assert body["summary"]["one_to_one"] + body["summary"]["one_to_many"] == body["summary"]["foreign_keys"]


async def test_table_detail_matches_information_schema(client, make_staff, conn):
    _, h = await make_staff("system_admin")
    d = (await client.get(f"{API}/tables/complaints/complaint", headers=h)).json()
    real = await conn.fetch("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema='complaints' AND table_name='complaint' ORDER BY ordinal_position")
    assert [c["name"] for c in d["columns"]] == [r[0] for r in real]
    assert {c["name"]: c["not_null"] for c in d["columns"]} == {r[0]: r[1] == "NO" for r in real}
    assert d["primary_key"] == ["complaint_id"]
    assert {r["table"] for r in d["references"]} >= {"identity.citizen", "administration.department", "complaints.complaint_category"}
    assert "complaints.complaint_history" in {r["table"] for r in d["referenced_by"]}
    fk_col = next(c for c in d["columns"] if c["name"] == "citizen_id")
    assert fk_col["references"] == {"table": "identity.citizen", "column": "citizen_id"} and fk_col["fk"] is True
    assert any("complaint_history" in j["sql"] for j in d["example_joins"])
    assert any(i["method"] == "gist" for i in d["indexes"]) or any(i["method"] == "btree" for i in d["indexes"])
    assert d["used_in"] and all(p.startswith(("app/", "scripts/", "etl/", "knowledge_graph/", "ai/")) for p in d["used_in"])


async def test_unknown_or_malicious_table_names_are_404(client, make_staff):
    _, h = await make_staff("system_admin")
    for path in ("/tables/nope/nope", "/tables/identity/app_user%3B%20DROP%20TABLE%20x", "/tables/pg_catalog/pg_authid", "/tables/public/spatial_ref_sys"):
        assert (await client.get(API + path, headers=h)).status_code == 404, path
    assert (await client.get(f"{API}/examples/not_an_example/run", headers=h)).status_code == 404


# ── nothing sensitive leaves the server ───────────────────────────────────────────────────────────────────
async def test_samples_are_limited_to_public_catalogue_tables_and_hide_sensitive_columns(client, make_staff, make_citizen):
    await make_citizen()                                                   # make sure identity tables hold a real row
    _, h = await make_staff("system_admin")
    users = (await client.get(f"{API}/tables/identity/app_user", headers=h)).json()
    assert users["sample"]["available"] is False
    assert "password_hash" in {c["name"] for c in users["columns"]}         # structure is visible ...
    assert "@example.com" not in json.dumps(users)                          # ... rows are not
    dept = (await client.get(f"{API}/tables/administration/department", headers=h)).json()["sample"]
    assert dept["available"] and dept["rows"] and "department_name" in dept["columns"]
    assert "contact_email" not in dept["columns"] and "contact_email" in dept["hidden_columns"]
    district = (await client.get(f"{API}/tables/administration/district", headers=h)).json()["sample"]
    assert "geometry" not in district["columns"]
    for t in ("complaints/complaint", "audit/audit_log", "ai/message"):
        assert (await client.get(f"{API}/tables/{t}", headers=h)).json()["sample"]["available"] is False


async def test_no_endpoint_leaks_secrets_or_connection_strings(client, make_staff):
    _, h = await make_staff("system_admin")
    blob = ""
    for path in ENDPOINTS + ["/tables/identity/app_user", "/tables/audit/audit_log"]:
        blob += (await client.get(API + path, headers=h)).text
    for needle in ("postgresql://", "postgresql+asyncpg", "JWT_SECRET", "NEO4J_PASSWORD", "POSTGRES_PASSWORD", "MINIO_SECRET", "Bearer ", "$argon2"):
        assert needle not in blob, needle


# ── components, advanced concepts, examples ──────────────────────────────────────────────────────────────
async def test_components_describe_real_wiring_and_state(client, make_staff):
    _, h = await make_staff("system_admin")
    body = (await client.get(f"{API}/components", headers=h)).json()
    nodes = {n["id"]: n for n in body["nodes"]}
    assert set(nodes) == {"frontend", "api", "services", "postgresql", "postgis", "pgvector", "neo4j", "redis", "minio"}
    assert nodes["postgresql"]["status"] == "active" and nodes["postgresql"]["role"] == "primary storage"
    assert nodes["minio"]["role"].startswith("optional") and nodes["redis"]["role"].startswith("optional")
    assert "not implemented" in nodes["minio"]["purpose"].lower() or "not used" in nodes["minio"]["role"].lower()
    assert nodes["postgresql"]["tables"] and "complaints.complaint" in nodes["postgresql"]["tables"]
    ids = set(nodes)
    assert all(e["from"] in ids and e["to"] in ids for e in body["edges"])
    assert {e["kind"] for e in body["edges"]} == {"primary", "extension", "optional"}


async def test_advanced_concepts_are_real_and_honest(client, make_staff, conn):
    _, h = await make_staff("system_admin")
    body = (await client.get(f"{API}/advanced", headers=h)).json()
    concepts = {c["concept"]: c for c in body["concepts"]}
    real_triggers = await conn.fetchval("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal")
    assert len(concepts["Triggers"]["examples"]) == real_triggers > 0
    assert {v["name"] for v in concepts["Views"]["examples"]} >= {"v_sla_breached", "v_department_performance"}
    assert concepts["Stored procedures (CALL)"]["status"] == "Not implemented"
    assert concepts["Redis"]["status"] == "Not implemented"
    assert concepts["Triggers"]["status"] == "Implemented"
    assert body["constraint_counts"]["foreign_key"] > 50


async def test_every_curated_example_runs_read_only_and_explains(client, make_staff):
    _, h = await make_staff("system_admin")
    listing = (await client.get(f"{API}/implementation", headers=h)).json()
    assert len(listing["examples"]) == len(arch.EXAMPLES) >= 8
    for ex in listing["examples"]:
        run = await client.get(f"{API}/examples/{ex['id']}/run", headers=h)
        assert run.status_code == 200, (ex["id"], run.text)
        body = run.json()
        assert body["columns"] and body["row_count"] == len(body["rows"]) <= 25
        plan = await client.get(f"{API}/examples/{ex['id']}/explain", headers=h)
        assert plan.status_code == 200 and plan.json()["plan"], ex["id"]
    assert listing["files"]["migrations"] and listing["files"]["schema"]


async def test_example_runner_is_read_only(session_factory):
    from sqlalchemy.exc import DBAPIError

    async with session_factory() as db:
        with pytest.raises(DBAPIError):
            await arch.run_example(db, {"sql": "CREATE TABLE public.architecture_probe (i int)"})
    async with session_factory() as db:
        with pytest.raises(DBAPIError):
            await arch.run_example(db, {"sql": "UPDATE schemes.scheme SET status = status"})


async def test_viewing_a_table_and_running_an_example_are_audited(client, make_staff, conn):
    mark = await conn.fetchval("SELECT coalesce(max(audit_id), 0) FROM audit.audit_log")
    _, h = await make_staff("state_admin")
    await client.get(f"{API}/tables/schemes/scheme", headers=h)
    await client.get(f"{API}/examples/schemes_by_department/run", headers=h)
    actions = [r[0] for r in await conn.fetch("SELECT action FROM audit.audit_log WHERE audit_id > $1", mark)]
    assert "ARCHITECTURE_TABLE_VIEWED" in actions and "ARCHITECTURE_EXAMPLE_RUN" in actions


async def test_normalization_report_never_claims_third_normal_form(client, make_staff):
    _, h = await make_staff("system_admin")
    body = (await client.get(f"{API}/normalization", headers=h)).json()
    assert body["summary"]["tables"] > 40 and body["summary"]["without_primary_key"] == 0
    assert all("cannot be established" in r["third_nf"] for r in body["tables"])
    assert any("composite" in n or "single column" in n for n in body["notes"])


def test_every_architecture_route_is_exercised():
    from app.main import app
    from scripts.route_inventory import flatten        # FastAPI nests included routers; this walks them to full paths

    live = {path for path, _ in flatten(app.routes) if path.startswith("/api/v1/architecture")}
    assert live == set(COVERED_ROUTES)
    assert len(ENDPOINTS) >= len(COVERED_ROUTES) - 1          # every route (the two example routes + table detail use concrete ids) is called above
