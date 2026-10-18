"""Rebuild the Neo4j knowledge graph from the relational database.   python -m knowledge_graph.rebuild

PostgreSQL stays the single source of truth; the graph is a disposable analytic projection and no part
of the core application depends on it. The rebuild is idempotent (MERGE on unique keys) and consistent:
every node/edge written in a run is stamped with the run id and, only after ALL batches succeeded,
managed nodes from earlier runs that no longer exist in PostgreSQL are deleted. A failed run therefore
leaves the previous graph intact.

Model                                            Source
  (Department)<-[:ADMINISTERED_BY]-(Scheme)      schemes.scheme.department_id
  (Department)<-[:PROVIDED_BY]-(Service)         services.service.department_id
  (Authority)-[:BELONGS_TO]->(Department)        administration.authority
  (Authority)-[:ESCALATES_TO]->(Authority)       authority.parent_authority_id
  (Category)-[:ROUTES_TO]->(Department)          complaints.routing_rule
  (Complaint)-[:IN_CATEGORY]->(Category)         complaints.complaint
  (Complaint)-[:ROUTED_TO]->(Authority)          complaint.authority_id (only if assigned)
  (Document)-[:ISSUED_BY]->(Department)          documents.document.department_id (only if recorded)
  (Citizen)-[:ELIGIBLE_FOR]->(Scheme)            see below

Privacy: complaint nodes carry reference, status, priority and date only - never text, title, address or
citizen. A Citizen node exists only for citizens with recorded profile consent, is keyed by a keyed hash
(GRAPH_PSEUDONYM_SECRET; without it no citizen data is exported) and holds no attributes. ELIGIBLE_FOR is
written only when the deterministic rule engine proves it: some rule group of the scheme has all its
mandatory rules PASS on the citizen's own recorded facts. Missing facts mean no edge - never a guess.
Synthetic (generated) records are excluded.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid
from datetime import date, datetime, timezone
from urllib.parse import quote

import asyncpg

from app.core.config import settings
from app.services.scheme_service import evaluate_rule

LABELS = ("Department", "Scheme", "Service", "Authority", "Category", "Complaint", "Document", "Citizen")
KEYS = {"Department": "code", "Scheme": "code", "Service": "code", "Authority": "id", "Category": "code",
        "Complaint": "ref", "Document": "id", "Citizen": "key"}
BATCH = 500


def pseudonym(secret: str, citizen_id) -> str:
    return hmac.new(secret.encode(), str(citizen_id).encode(), hashlib.sha256).hexdigest()[:24]


def profile_facts(profile: dict, today: date | None = None) -> dict:
    """Facts the rule engine may use, derived ONLY from what the citizen recorded (age from date of birth)."""
    facts = {k: v for k, v in profile.items() if v is not None and k != "date_of_birth"}
    dob = profile.get("date_of_birth")
    if dob:
        t = today or datetime.now(timezone.utc).date()
        facts["age"] = t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))
    return facts


def eligible_rules(rules: list[dict], facts: dict) -> list[str] | None:
    """Rule ids proving eligibility, or None. Eligible iff some group has >=1 mandatory rule and all PASS."""
    groups: dict[int, list[dict]] = {}
    for r in rules:
        groups.setdefault(r["rule_group"], []).append(r)
    for g in groups.values():
        mandatory = [r for r in g if r["mandatory"]]
        if mandatory and all(evaluate_rule(r, facts) == "PASS" for r in mandatory):
            return [str(r["rule_id"]) for r in mandatory]
    return None


# ── extraction (PostgreSQL -> plain dicts) ─────────────────────────────────────────────────────────
async def extract(conn, *, pseudonym_secret: str | None, today: date | None = None) -> dict:
    d: dict = {}
    d["departments"] = [dict(r) for r in await conn.fetch(
        "SELECT department_code AS code, department_name AS name, verification_status AS status FROM administration.department")]
    d["schemes"] = [dict(r) for r in await conn.fetch(
        "SELECT s.scheme_code AS code, s.scheme_name AS name, s.scheme_level AS level, s.verification_status AS status, d.department_code AS dept "
        "FROM schemes.scheme s LEFT JOIN administration.department d USING (department_id) WHERE s.status='active'")]
    d["services"] = [dict(r) for r in await conn.fetch(
        "SELECT s.service_code AS code, s.service_name AS name, s.verification_status AS status, d.department_code AS dept "
        "FROM services.service s LEFT JOIN administration.department d USING (department_id) WHERE s.status='active' AND s.service_code IS NOT NULL")]
    d["authorities"] = [dict(r) for r in await conn.fetch(
        "SELECT a.authority_id::text AS id, a.authority_name AS name, a.jurisdiction_level AS level, a.is_routing_placeholder AS placeholder, "
        "d.department_code AS dept, a.parent_authority_id::text AS parent FROM administration.authority a JOIN administration.department d USING (department_id)")]
    d["categories"] = [dict(r) for r in await conn.fetch(
        "SELECT c.category_code AS code, c.category_name AS name, d.department_code AS dept "
        "FROM complaints.complaint_category c LEFT JOIN administration.department d ON d.department_id=c.default_department_id")]
    d["routes"] = [dict(r) for r in await conn.fetch(
        "SELECT DISTINCT c.category_code AS category, d.department_code AS dept FROM complaints.routing_rule r "
        "JOIN complaints.complaint_category c USING (category_id) JOIN administration.department d ON d.department_id=r.department_id")]
    d["complaints"] = [dict(r) for r in await conn.fetch(
        "SELECT c.complaint_ref AS ref, c.status, c.priority, c.created_at::date::text AS created, cc.category_code AS category, "
        "c.authority_id::text AS authority FROM complaints.complaint c LEFT JOIN complaints.complaint_category cc USING (category_id) "
        "WHERE NOT c.is_synthetic")]
    d["documents"] = [dict(r) for r in await conn.fetch(
        "SELECT x.document_id::text AS id, x.title, x.document_type AS type, x.verification_status AS status, dep.department_code AS dept "
        "FROM documents.document x LEFT JOIN administration.department dep USING (department_id) "
        "WHERE x.status='active' AND x.extraction_status='ok'")]
    d["citizens"], d["eligible"], d["notes"] = [], [], []
    if not pseudonym_secret:
        d["notes"].append("GRAPH_PSEUDONYM_SECRET is not set: no Citizen nodes or ELIGIBLE_FOR edges were exported.")
        return d
    rules_by_scheme: dict[str, list[dict]] = {}
    for r in await conn.fetch(
            "SELECT s.scheme_code, er.rule_id, er.rule_group, er.attribute, er.operator, er.value, er.mandatory "
            "FROM schemes.eligibility_rule er JOIN schemes.scheme s USING (scheme_id) WHERE s.status='active' "
            "AND (er.effective_from IS NULL OR er.effective_from <= CURRENT_DATE) AND (er.effective_to IS NULL OR er.effective_to >= CURRENT_DATE)"):
        value = r["value"]
        rules_by_scheme.setdefault(r["scheme_code"], []).append({
            "rule_id": r["rule_id"], "rule_group": r["rule_group"], "attribute": r["attribute"], "operator": r["operator"],
            "value": json.loads(value) if isinstance(value, str) else value, "mandatory": r["mandatory"]})
    status = {s["code"]: s["status"] for s in d["schemes"]}
    rows = await conn.fetch(
        "SELECT c.citizen_id, p.date_of_birth, p.gender, p.occupation, p.is_student, p.annual_income::float AS annual_income, "
        "p.social_category, p.disability_status, p.bpl_status, p.residence_type, p.district_id, p.education_level, p.marital_status, p.family_size "
        "FROM identity.citizen c JOIN identity.citizen_profile p USING (citizen_id) "
        "WHERE NOT c.is_synthetic AND coalesce((SELECT granted FROM identity.consent k WHERE k.citizen_id=c.citizen_id "
        "AND k.purpose='profile_based_scheme_matching' ORDER BY granted_at DESC, consent_id LIMIT 1), false)")
    for row in rows:
        facts = profile_facts({k: v for k, v in dict(row).items() if k != "citizen_id"}, today)
        key = pseudonym(pseudonym_secret, row["citizen_id"])
        d["citizens"].append({"key": key})
        for code, rules in rules_by_scheme.items():
            basis = eligible_rules(rules, facts)
            if basis:
                d["eligible"].append({"citizen": key, "scheme": code, "basis": basis, "scheme_status": status.get(code, "unknown")})
    return d


# ── load (parameterised Cypher) ───────────────────────────────────────────────────────────────────────
def cypher_statements() -> list[tuple[str, str]]:
    """(name, cypher) pairs; every statement takes $rows and $run only - no string interpolation of data."""
    def node(label, extra=""):
        key = KEYS[label]
        return (f"UNWIND $rows AS r MERGE (n:{label} {{{key}: r.{key}}}) SET n += r{extra}, n.run = $run")

    return [
        ("Department", node("Department")), ("Scheme", node("Scheme")), ("Service", node("Service")),
        ("Authority", node("Authority")), ("Category", node("Category")), ("Complaint", node("Complaint")),
        ("Document", node("Document")), ("Citizen", node("Citizen")),
        ("ADMINISTERED_BY", "UNWIND $rows AS r MATCH (s:Scheme {code: r.code}) MATCH (d:Department {code: r.dept}) MERGE (s)-[e:ADMINISTERED_BY]->(d) SET e.run = $run"),
        ("PROVIDED_BY", "UNWIND $rows AS r MATCH (s:Service {code: r.code}) MATCH (d:Department {code: r.dept}) MERGE (s)-[e:PROVIDED_BY]->(d) SET e.run = $run"),
        ("BELONGS_TO", "UNWIND $rows AS r MATCH (a:Authority {id: r.id}) MATCH (d:Department {code: r.dept}) MERGE (a)-[e:BELONGS_TO]->(d) SET e.run = $run"),
        ("ESCALATES_TO", "UNWIND $rows AS r MATCH (a:Authority {id: r.id}) MATCH (p:Authority {id: r.parent}) MERGE (a)-[e:ESCALATES_TO]->(p) SET e.run = $run"),
        ("ROUTES_TO", "UNWIND $rows AS r MATCH (c:Category {code: r.category}) MATCH (d:Department {code: r.dept}) MERGE (c)-[e:ROUTES_TO]->(d) SET e.run = $run"),
        ("IN_CATEGORY", "UNWIND $rows AS r MATCH (c:Complaint {ref: r.ref}) MATCH (k:Category {code: r.category}) MERGE (c)-[e:IN_CATEGORY]->(k) SET e.run = $run"),
        ("ROUTED_TO", "UNWIND $rows AS r MATCH (c:Complaint {ref: r.ref}) MATCH (a:Authority {id: r.authority}) MERGE (c)-[e:ROUTED_TO]->(a) SET e.run = $run"),
        ("ISSUED_BY", "UNWIND $rows AS r MATCH (x:Document {id: r.id}) MATCH (d:Department {code: r.dept}) MERGE (x)-[e:ISSUED_BY]->(d) SET e.run = $run"),
        ("ELIGIBLE_FOR", "UNWIND $rows AS r MATCH (c:Citizen {key: r.citizen}) MATCH (s:Scheme {code: r.scheme}) "
                         "MERGE (c)-[e:ELIGIBLE_FOR]->(s) SET e.run = $run, e.basis_rule_ids = r.basis, e.scheme_status = r.scheme_status"),
    ]


def plan_rows(data: dict) -> dict[str, list[dict]]:
    """Rows per statement name."""
    pick = lambda rows, *keys: [{k: r[k] for k in keys} for r in rows]  # noqa: E731
    return {
        "Department": pick(data["departments"], "code", "name", "status"),
        "Scheme": pick(data["schemes"], "code", "name", "level", "status"),
        "Service": pick(data["services"], "code", "name", "status"),
        "Authority": pick(data["authorities"], "id", "name", "level", "placeholder"),
        "Category": pick(data["categories"], "code", "name"),
        "Complaint": pick(data["complaints"], "ref", "status", "priority", "created"),
        "Document": pick(data["documents"], "id", "title", "type", "status"),
        "Citizen": pick(data["citizens"], "key"),
        "ADMINISTERED_BY": [r for r in data["schemes"] if r["dept"]],
        "PROVIDED_BY": [r for r in data["services"] if r["dept"]],
        "BELONGS_TO": pick(data["authorities"], "id", "dept"),
        "ESCALATES_TO": [r for r in data["authorities"] if r["parent"]],
        "ROUTES_TO": [{"category": c["code"], "dept": c["dept"]} for c in data["categories"] if c["dept"]] + data["routes"],
        "IN_CATEGORY": [r for r in data["complaints"] if r["category"]],
        "ROUTED_TO": [r for r in data["complaints"] if r["authority"]],
        "ISSUED_BY": [r for r in data["documents"] if r["dept"]],
        "ELIGIBLE_FOR": data["eligible"],
    }


async def load(driver, data: dict, run: str) -> dict:
    """Apply constraints and MERGE everything; sweep stale managed nodes only after full success."""
    counts: dict[str, int] = {}
    async with driver.session() as session:
        for label, key in KEYS.items():
            await session.run(f"CREATE CONSTRAINT {label.lower()}_{key}_unique IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")
        rows_by_name = plan_rows(data)
        for name, cypher in cypher_statements():
            rows = rows_by_name[name]
            for i in range(0, len(rows), BATCH):
                await session.run(cypher, rows=rows[i:i + BATCH], run=run)
            counts[name] = len(rows)
        # --- everything above succeeded: remove what PostgreSQL no longer contains
        removed = 0
        for label in LABELS:
            res = await session.run(f"MATCH (n:{label}) WHERE n.run IS NULL OR n.run <> $run DETACH DELETE n RETURN count(n) AS c", run=run)
            removed += (await res.single())["c"]
        await session.run("MATCH ()-[e]->() WHERE e.run IS NULL OR e.run <> $run DELETE e", run=run)
    counts["stale_nodes_removed"] = removed
    return counts


async def summarise(driver) -> dict:
    async with driver.session() as session:
        nodes = {r["l"]: r["c"] async for r in await session.run("MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c")}
        rels = {r["t"]: r["c"] async for r in await session.run("MATCH ()-[e]->() RETURN type(e) AS t, count(*) AS c")}
    return {"nodes": nodes, "relationships": rels}


def default_dsn() -> str:
    g = os.getenv
    return "postgresql://{u}:{p}@{h}:{port}/{db}".format(
        u=quote(g("POSTGRES_USER", settings.POSTGRES_USER)), p=quote(g("POSTGRES_PASSWORD", settings.POSTGRES_PASSWORD)),
        h=g("POSTGRES_HOST", settings.POSTGRES_HOST), port=g("POSTGRES_PORT", str(settings.POSTGRES_PORT)),
        db=g("POSTGRES_DB", settings.POSTGRES_DB))


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn")
    ap.add_argument("--dry-run", action="store_true", help="extract and report counts; do not touch Neo4j")
    args = ap.parse_args(argv)
    secret = os.getenv("GRAPH_PSEUDONYM_SECRET") or None
    conn = await asyncpg.connect((args.dsn or default_dsn()).replace("postgresql+asyncpg://", "postgresql://"))
    try:
        data = await extract(conn, pseudonym_secret=secret)
    finally:
        await conn.close()
    rows = plan_rows(data)
    print({k: len(v) for k, v in rows.items()})
    for n in data["notes"]:
        print("note:", n)
    if args.dry_run:
        return 0
    try:
        from neo4j import AsyncGraphDatabase
        from neo4j.exceptions import Neo4jError, ServiceUnavailable
    except ImportError:
        print("error: the neo4j driver is not installed", file=sys.stderr)
        return 2
    driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
    try:
        await driver.verify_connectivity()
        counts = await load(driver, data, uuid.uuid4().hex)
        print({"loaded": counts, "graph": await summarise(driver)})
        return 0
    except (ServiceUnavailable, OSError) as e:
        print(f"error: cannot reach Neo4j at {settings.NEO4J_URI}: {e}", file=sys.stderr)
        return 3
    except Neo4jError as e:
        print(f"error: Neo4j rejected the load; the previous graph was left in place: {e.message}", file=sys.stderr)
        return 4
    finally:
        await driver.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
