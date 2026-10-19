"""Knowledge-graph rebuild: extraction rules, privacy, idempotence, consistency, failure safety.

Tests marked `neo4j` need a DISPOSABLE Neo4j and run only when TEST_NEO4J_URI (plus TEST_NEO4J_USER /
TEST_NEO4J_PASSWORD) is set - they delete every node in that instance.
"""
import os
import re
import uuid
from datetime import date

import pytest
import pytest_asyncio

from knowledge_graph import rebuild as kg

DAY = date(2026, 10, 19)


# -- pure rules -------------------------------------------------------------------------------------
def test_pseudonym_is_keyed_stable_and_hides_the_id():
    cid = uuid.uuid4()
    a, b = kg.pseudonym("secret-1", cid), kg.pseudonym("secret-2", cid)
    assert a == kg.pseudonym("secret-1", cid) and a != b and str(cid).replace("-", "") not in a and len(a) == 24


def test_age_is_derived_from_date_of_birth_only():
    f = kg.profile_facts({"date_of_birth": date(2000, 10, 20), "gender": "female", "income": None}, DAY)
    assert f["age"] == 25 and f["gender"] == "female" and "date_of_birth" not in f and "income" not in f
    assert kg.profile_facts({"date_of_birth": date(2000, 10, 19)}, DAY)["age"] == 26      # birthday today
    assert "age" not in kg.profile_facts({"gender": "male"}, DAY)


def rule(group, attr, op, value, mandatory=True):
    return {"rule_id": uuid.uuid4(), "rule_group": group, "attribute": attr, "operator": op, "value": value, "mandatory": mandatory}


def test_eligibility_requires_a_fully_passing_group_of_mandatory_rules():
    r1, r2 = rule(1, "age", ">=", 18), rule(1, "annual_income", "<=", 100000)
    assert kg.eligible_rules([r1, r2], {"age": 30, "annual_income": 50000}) == [str(r1["rule_id"]), str(r2["rule_id"])]
    assert kg.eligible_rules([r1, r2], {"age": 30, "annual_income": 500000}) is None        # FAIL
    assert kg.eligible_rules([r1, r2], {"age": 30}) is None                                    # UNKNOWN is never a guess
    alt = rule(2, "social_category", "IN", ["SC", "ST"])
    assert kg.eligible_rules([r1, r2, alt], {"age": 10, "annual_income": 1, "social_category": "sc"}) == [str(alt["rule_id"])]   # OR across groups
    assert kg.eligible_rules([rule(1, "age", ">=", 18, mandatory=False)], {"age": 30}) is None  # nothing mandatory proven
    assert kg.eligible_rules([], {"age": 30}) is None


def test_all_cypher_is_parameterised_and_run_stamped():
    for name, cypher in kg.cypher_statements():
        assert "$rows" in cypher and "$run" in cypher, name
        assert not re.search(r"['\"][^'\"]*(?:\{|\+)\s*\w+", cypher), name         # no data interpolated into the text


def test_plan_covers_every_statement():
    data = {k: [] for k in ("departments", "schemes", "services", "authorities", "categories", "routes", "complaints",
                            "documents", "citizens", "eligible")}
    assert {n for n, _ in kg.cypher_statements()} == set(kg.plan_rows(data))


# -- extraction from PostgreSQL ----------------------------------------------------------------------
@pytest_asyncio.fixture
async def citizens(conn):
    made = []

    async def add(*, consent, profile, synthetic=False):
        uid = uuid.uuid4()
        await conn.execute("INSERT INTO identity.app_user (user_id,email,password_hash,role,is_synthetic) VALUES ($1,$2,'x','citizen',$3)",
                           uid, f"kg-{uid.hex[:8]}@{'synthetic.invalid' if synthetic else 'example.com'}", synthetic)
        cid = await conn.fetchval("INSERT INTO identity.citizen (user_id,name,is_synthetic,synthetic_batch) VALUES ($1,'KG Test',$2,$3) RETURNING citizen_id",
                                  uid, synthetic, "kg" if synthetic else None)
        await conn.execute("INSERT INTO identity.citizen_profile (citizen_id,date_of_birth,annual_income,social_category,gender) VALUES ($1,$2,$3,$4,'female')",
                           cid, profile.get("dob", date(1990, 1, 1)), profile.get("income"), profile.get("category"))
        if consent is not None:
            await conn.execute("INSERT INTO identity.consent (citizen_id,purpose,granted) VALUES ($1,'profile_based_scheme_matching',$2)", cid, consent)
        made.append((cid, uid))
        return cid

    yield add
    for cid, uid in made:
        await conn.execute("DELETE FROM identity.consent WHERE citizen_id=$1", cid)
        await conn.execute("DELETE FROM identity.citizen_profile WHERE citizen_id=$1", cid)
        await conn.execute("DELETE FROM identity.citizen WHERE citizen_id=$1", cid)
        await conn.execute("DELETE FROM identity.app_user WHERE user_id=$1", uid)
    await conn.execute("DELETE FROM schemes.eligibility_rule WHERE source_reference='kg-test'")


async def with_rules(conn):
    sid = await conn.fetchval("SELECT scheme_id FROM schemes.scheme WHERE scheme_code='TN-FREE-BUS-PASS'")
    await conn.execute("INSERT INTO schemes.eligibility_rule (scheme_id,rule_group,attribute,operator,value,source_reference) VALUES "
                       "($1,1,'age','>=','18'::jsonb,'kg-test'), ($1,1,'annual_income','<=','200000'::jsonb,'kg-test')", sid)


@pytest.mark.db
async def test_extraction_without_secret_exports_no_citizen_data(conn, citizens):
    await citizens(consent=True, profile={"income": 1000})
    d = await kg.extract(conn, pseudonym_secret=None, today=DAY)
    assert d["citizens"] == [] and d["eligible"] == [] and "GRAPH_PSEUDONYM_SECRET" in d["notes"][0]


@pytest.mark.db
async def test_eligibility_edges_only_for_consenting_citizens_with_proving_facts(conn, citizens):
    await with_rules(conn)
    yes = await citizens(consent=True, profile={"income": 100000})
    no_income = await citizens(consent=True, profile={"income": 900000})
    unknown = await citizens(consent=True, profile={"income": None})
    no_consent = await citizens(consent=None, profile={"income": 100000})
    revoked = await citizens(consent=False, profile={"income": 100000})
    synthetic = await citizens(consent=True, profile={"income": 100000}, synthetic=True)
    d = await kg.extract(conn, pseudonym_secret="s3cret", today=DAY)
    key = lambda c: kg.pseudonym("s3cret", c)  # noqa: E731
    exported = {c["key"] for c in d["citizens"]}
    assert key(yes) in exported and key(no_income) in exported and key(unknown) in exported
    assert not exported & {key(no_consent), key(revoked), key(synthetic)}              # consent + synthetic filters
    edges = [e for e in d["eligible"] if e["citizen"] in (key(yes), key(no_income), key(unknown))]
    assert [(e["citizen"], e["scheme"]) for e in edges] == [(key(yes), "TN-FREE-BUS-PASS")]
    assert len(edges[0]["basis"]) == 2 and edges[0]["scheme_status"] == "provisional"   # carries the rules' (provisional) status
    flat = repr(d["citizens"]) + repr(d["eligible"])
    assert str(yes) not in flat and "KG Test" not in flat and "example.com" not in flat


@pytest.mark.db
async def test_complaint_and_document_rows_carry_no_personal_or_free_text_data(conn, make_citizen, client):
    c = await make_citizen("Private Name")
    await client.post("/api/v1/complaints", headers=c["headers"], json={"title": "Secret title", "description": "Secret details about my house", "address": "12 Secret Street"})
    d = await kg.extract(conn, pseudonym_secret="s", today=DAY)
    rows = kg.plan_rows(d)["Complaint"]
    assert rows and set(rows[0]) == {"ref", "status", "priority", "created"}
    assert "Secret" not in repr(d["complaints"]) and "Private Name" not in repr(d)


@pytest.mark.db
async def test_synthetic_complaints_are_excluded(conn):
    d = await kg.extract(conn, pseudonym_secret=None, today=DAY)
    syn = await conn.fetchval("SELECT count(*) FROM complaints.complaint WHERE is_synthetic")
    real = await conn.fetchval("SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic")
    assert len(d["complaints"]) == real and syn >= 0


# -- Neo4j-backed ------------------------------------------------------------------------------------------
NEO = pytest.mark.skipif(not os.getenv("TEST_NEO4J_URI"), reason="BLOCKED: set TEST_NEO4J_URI to a disposable Neo4j to run")


@pytest_asyncio.fixture
async def graph():
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(os.environ["TEST_NEO4J_URI"],
                                       auth=(os.getenv("TEST_NEO4J_USER", "neo4j"), os.environ["TEST_NEO4J_PASSWORD"]))
    async with driver.session() as s:
        await s.run("MATCH (n) DETACH DELETE n")
    yield driver
    async with driver.session() as s:
        await s.run("MATCH (n) DETACH DELETE n")
    await driver.close()


async def cypher_value(driver, query, **params):
    async with driver.session() as s:
        return (await (await s.run(query, **params)).single())[0]


@NEO
@pytest.mark.db
async def test_load_builds_the_expected_graph(conn, graph):
    d = await kg.extract(conn, pseudonym_secret=None, today=DAY)
    await kg.load(graph, d, "run1")
    assert await cypher_value(graph, "MATCH (s:Scheme) RETURN count(s)") == len(d["schemes"])
    assert await cypher_value(graph, "MATCH (d:Department) RETURN count(d)") == len(d["departments"])
    # relationships reflect relational foreign keys
    assert await cypher_value(graph, "MATCH (:Scheme {code:'TN-CM-BREAKFAST'})-[:ADMINISTERED_BY]->(d:Department) RETURN d.code") == \
        await conn.fetchval("SELECT d.department_code FROM schemes.scheme s JOIN administration.department d USING (department_id) WHERE s.scheme_code='TN-CM-BREAKFAST'")
    assert await cypher_value(graph, "MATCH (:Authority)-[:BELONGS_TO]->(:Department) RETURN count(*)") == len(d["authorities"])
    assert await cypher_value(graph, "MATCH (:Category)-[:ROUTES_TO]->(:Department) RETURN count(*)") >= 1
    assert await cypher_value(graph, "MATCH (n:Citizen) RETURN count(n)") == 0                   # no secret -> none


@NEO
@pytest.mark.db
async def test_rebuild_is_idempotent_with_no_duplicates(conn, graph):
    d = await kg.extract(conn, pseudonym_secret=None, today=DAY)
    await kg.load(graph, d, "a")
    first = await kg.summarise(graph)
    await kg.load(graph, d, "b")
    await kg.load(graph, d, "c")
    assert await kg.summarise(graph) == first
    assert await cypher_value(graph, "MATCH (s:Scheme) WITH s.code AS c, count(*) AS n WHERE n > 1 RETURN count(*)") == 0


@NEO
@pytest.mark.db
async def test_graph_follows_the_database_and_removes_stale_nodes(conn, graph):
    d = await kg.extract(conn, pseudonym_secret=None, today=DAY)
    await kg.load(graph, d, "a")
    d["schemes"] = [s for s in d["schemes"] if s["code"] != "TN-PM-KISAN"]            # as if deleted in PostgreSQL
    counts = await kg.load(graph, d, "b")
    assert counts["stale_nodes_removed"] >= 1
    assert await cypher_value(graph, "MATCH (s:Scheme {code:'TN-PM-KISAN'}) RETURN count(s)") == 0
    assert await cypher_value(graph, "MATCH (s:Scheme) RETURN count(s)") == len(d["schemes"])


@NEO
@pytest.mark.db
async def test_failed_load_leaves_the_previous_graph_intact(conn, graph):
    from neo4j.exceptions import Neo4jError

    d = await kg.extract(conn, pseudonym_secret=None, today=DAY)
    await kg.load(graph, d, "good")
    before = await kg.summarise(graph)
    bad = {**d, "services": d["services"] + [{"code": None, "name": "broken", "status": "x", "dept": None}]}   # MERGE on null key
    with pytest.raises(Neo4jError):
        await kg.load(graph, bad, "bad")
    after = await kg.summarise(graph)
    assert after == before                                                         # nothing swept, nothing lost
    await kg.load(graph, d, "recovered")                                          # and the next good run converges cleanly
    assert await kg.summarise(graph) == before
    assert await cypher_value(graph, "MATCH (n) WHERE n.run <> 'recovered' RETURN count(n)") == 0


@NEO
@pytest.mark.db
async def test_eligibility_edges_and_pseudonyms_in_the_graph(conn, graph, citizens):
    await with_rules(conn)
    cid = await citizens(consent=True, profile={"income": 100000})
    d = await kg.extract(conn, pseudonym_secret="s3cret", today=DAY)
    await kg.load(graph, d, "r")
    key = kg.pseudonym("s3cret", cid)
    assert await cypher_value(graph, "MATCH (:Citizen {key:$k})-[e:ELIGIBLE_FOR]->(s:Scheme) RETURN s.code", k=key) == "TN-FREE-BUS-PASS"
    props = await cypher_value(graph, "MATCH (c:Citizen {key:$k}) RETURN keys(c)", k=key)
    assert sorted(props) == ["key", "run"]                                           # nothing but the pseudonym
    basis = await cypher_value(graph, "MATCH (:Citizen {key:$k})-[e:ELIGIBLE_FOR]->() RETURN e.basis_rule_ids", k=key)
    assert len(basis) == 2


@NEO
@pytest.mark.db
async def test_unreachable_neo4j_is_reported_not_crashed(test_db_dsn, monkeypatch, capsys):
    from app.core.config import settings

    monkeypatch.setattr(settings, "NEO4J_URI", "bolt://localhost:1")
    rc = await kg.main(["--dsn", test_db_dsn])
    assert rc == 3 and "cannot reach Neo4j" in capsys.readouterr().err


@pytest.mark.db
async def test_dry_run_never_touches_neo4j(test_db_dsn, monkeypatch, capsys):
    from app.core.config import settings

    monkeypatch.setattr(settings, "NEO4J_URI", "bolt://localhost:1")             # would fail if contacted
    assert await kg.main(["--dsn", test_db_dsn, "--dry-run"]) == 0
    assert "Scheme" in capsys.readouterr().out
