"""Create (or refresh) a self-contained DEMO database for presentations. Idempotent.

    python -m scripts.demo_env --admin-dsn postgresql://postgres@localhost:5432/postgres
    python -m scripts.demo_env --admin-dsn ... --reset          # drop and rebuild from scratch

What it builds, in database ``mygovt_dev_demo`` (a name the synthetic-data guard accepts):
* schema + migrations + the (provisional) seed - the same data every environment gets;
* demo officers (2 per routable department, SYNTHETIC), and demo logins for each role (password from
  DEMO_PASSWORD, default below - a FIXTURE credential for this throw-away database only);
* DEMO eligibility rules for five schemes, each labelled ``[DEMO RULE]`` with source "DEMO RULE - not an official criterion";
* clearly labelled synthetic citizens and complaints in every lifecycle state, some belonging to the demo citizen;
* officer assignments on the synthetic complaints that have progressed past triage.

Nothing here is official data. Government records stay ``provisional``; synthetic rows carry ``is_synthetic``.
Run the API with ``DEMO_INCLUDE_SYNTHETIC=true`` so staff lists and admin statistics include the demo complaints.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import uuid
from datetime import timedelta

import asyncpg

from app.security.jwt import hash_password
from scripts import db_verify, seed, synth_data

DB = "mygovt_dev_demo"
DEFAULT_PASSWORD = "Demo@12345"          # fixture credential for the disposable demo database only
DEMO_DOMAIN = "demo.example"

DEMO_RULES: dict[str, list[tuple[str, str, object, str]]] = {
    # scheme_id: [(attribute, operator, value, text)]
    "b0000001-0000-0000-0000-000000000002": [
        ("gender", "=", "female", "Applicant is a woman"),
        ("annual_income", "<=", 250000, "Annual family income up to Rs 2,50,000 (illustrative threshold)"),
    ],
    "b0000001-0000-0000-0000-000000000004": [
        ("gender", "=", "female", "Applicant is a woman"),
        ("is_student", "IS_TRUE", True, "Applicant is currently a student"),
    ],
    "b0000001-0000-0000-0000-000000000007": [
        ("occupation", "=", "farmer", "Applicant is a farmer"),
    ],
    "b0000001-0000-0000-0000-000000000008": [
        ("bpl_status", "IS_TRUE", True, "Household is below the poverty line"),
        ("annual_income", "<=", 120000, "Annual family income up to Rs 1,20,000 (illustrative threshold)"),
    ],
    "b0000001-0000-0000-0000-000000000009": [
        ("disability_status", "IS_TRUE", True, "Applicant has a certified disability"),
    ],
}

# (reference, title, scenario) for the demo citizen's own complaints
DEMO_CITIZEN_COMPLAINTS = [
    ("DEMO-0001", "Streetlight not working on my street", "open_new"),
    ("DEMO-0002", "Irregular drinking water supply", "in_progress"),
    ("DEMO-0003", "Pothole near the bus stand", "resolved_on_time"),
    ("DEMO-0004", "Garbage not collected for a week", "escalated"),
    ("DEMO-0005", "Delay in community certificate", "overdue_open"),
    ("DEMO-0006", "Drain overflow near the market", "closed"),
]


async def _upsert_user(conn, email: str, role: str, password: str, officer_id=None) -> uuid.UUID:
    row = await conn.fetchrow("SELECT user_id FROM identity.app_user WHERE email=$1", email)
    if row:
        await conn.execute("UPDATE identity.app_user SET password_hash=$2, role=$3, status='active', officer_id=$4 WHERE user_id=$1",
                           row["user_id"], hash_password(password), role, officer_id)
        return row["user_id"]
    return await conn.fetchval(
        "INSERT INTO identity.app_user (email,password_hash,role,status,officer_id) VALUES ($1,$2,$3,'active',$4) RETURNING user_id",
        email, hash_password(password), role, officer_id)


async def load_demo_rules(conn) -> int:
    """(Re)load the labelled DEMO eligibility rules; replaces only rules whose source starts with 'DEMO RULE'."""
    await conn.execute("DELETE FROM schemes.eligibility_rule WHERE source_reference LIKE 'DEMO RULE%'")
    n = 0
    for scheme_id, rules in DEMO_RULES.items():
        if not await conn.fetchval("SELECT 1 FROM schemes.scheme WHERE scheme_id=$1::uuid", scheme_id):
            continue
        for attribute, operator, value, text in rules:
            await conn.execute(
                "INSERT INTO schemes.eligibility_rule (scheme_id,rule_group,attribute,operator,value,mandatory,human_readable,source_reference) "
                "VALUES ($1::uuid,1,$2,$3,$4::jsonb,true,$5,'DEMO RULE - not an official criterion')",
                scheme_id, attribute, operator, json.dumps(value), f"[DEMO RULE] {text}")
            n += 1
    return n


async def build_database(admin_dsn: str, reset: bool, db: str = DB) -> str:
    admin = await asyncpg.connect(admin_dsn)
    try:
        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", db)
        if exists and reset:
            await admin.execute(f'DROP DATABASE "{db}" WITH (FORCE)')
            exists = None
        if not exists:
            await admin.execute(f'CREATE DATABASE "{db}"')
    finally:
        await admin.close()
    dsn = db_verify.with_db(admin_dsn, db)
    conn = await asyncpg.connect(dsn)
    try:
        if not await conn.fetchval("SELECT to_regclass('identity.app_user')"):
            await conn.execute(db_verify.SCHEMA.read_text(encoding="utf-8"))
            for m in db_verify.MIGRATIONS:
                await conn.execute(m.read_text(encoding="utf-8"))
        await seed.apply_seed(conn)
    finally:
        await conn.close()
    return dsn


async def populate(dsn: str, password: str) -> dict:
    conn = await asyncpg.connect(dsn)
    out: dict = {}
    try:
        depts = await conn.fetch(
            "SELECT DISTINCT d.department_id, d.department_name FROM complaints.complaint_category c "
            "JOIN administration.department d ON d.department_id = c.default_department_id "
            "WHERE c.is_active AND EXISTS (SELECT 1 FROM administration.authority a WHERE a.department_id = d.department_id) "
            "ORDER BY d.department_id")
        # --- officers (2 per routable department, synthetic) -------------------------------------
        officers: dict[int, list] = {}
        for d in depts:
            authority = await conn.fetchval(
                "SELECT authority_id FROM administration.authority WHERE department_id=$1 "
                "ORDER BY is_routing_placeholder DESC, authority_id LIMIT 1", d["department_id"])
            for n, designation in ((1, "Section Officer"), (2, "Assistant Engineer")):
                code = f"DEMO-{d['department_id']:02d}-{n}"
                oid = await conn.fetchval("SELECT officer_id FROM administration.officer WHERE employee_code=$1", code)
                if oid is None:
                    oid = await conn.fetchval(
                        "INSERT INTO administration.officer (department_id,authority_id,name,designation,employee_code,email,status) "
                        "VALUES ($1,$2,$3,$4,$5,$6,'active') RETURNING officer_id",
                        d["department_id"], authority, f"Demo Officer {d['department_id']}-{n}", designation, code,
                        f"{code.lower()}@{DEMO_DOMAIN}")
                officers.setdefault(d["department_id"], []).append(oid)
        out["officers"] = sum(len(v) for v in officers.values())

        # --- demo logins ---------------------------------------------------------------------------
        first, second = depts[0]["department_id"], depts[1]["department_id"]
        accounts = [
            ("officer@" + DEMO_DOMAIN, "officer", officers[first][0]),
            ("officer2@" + DEMO_DOMAIN, "officer", officers[second][0]),
            ("deptadmin@" + DEMO_DOMAIN, "department_admin", officers[first][1]),
            ("admin@" + DEMO_DOMAIN, "state_admin", None),
            ("sysadmin@" + DEMO_DOMAIN, "system_admin", None),
        ]
        for email, role, oid in accounts:
            await _upsert_user(conn, email, role, password, oid)

        citizen_email = f"citizen@{DEMO_DOMAIN}"
        uid = await _upsert_user(conn, citizen_email, "citizen", password)
        cid = await conn.fetchval("SELECT citizen_id FROM identity.citizen WHERE user_id=$1", uid)
        district = await conn.fetchval("SELECT district_id FROM administration.district ORDER BY district_id LIMIT 1")
        if cid is None:
            cid = await conn.fetchval("INSERT INTO identity.citizen (user_id,name) VALUES ($1,'Aarthi (demo citizen)') RETURNING citizen_id", uid)
            await conn.execute(
                "INSERT INTO identity.citizen_profile (citizen_id,gender,occupation,annual_income,social_category,residence_type,"
                "district_id,family_size,is_student,bpl_status,disability_status) "
                "VALUES ($1,'female','farmer',180000,'BC','rural',$2,4,false,false,false)", cid, district)
            await conn.execute("INSERT INTO identity.consent (citizen_id,purpose,granted) VALUES ($1,'profile_based_scheme_matching',true)", cid)

        n_rules = await load_demo_rules(conn)
        out["demo_eligibility_rules"] = n_rules

        # --- synthetic complaints ------------------------------------------------------------------
        cats = [r[0] for r in await conn.fetch(
            "SELECT c.category_id FROM complaints.complaint_category c WHERE c.is_active AND EXISTS "
            "(SELECT 1 FROM administration.authority a WHERE a.department_id = c.default_department_id) ORDER BY 1")]
        dists = [r[0] for r in await conn.fetch("SELECT district_id FROM administration.district ORDER BY 1")]
        batch, citizens, complaints = synth_data.plan(7, 12, 80, cats, dists)
        stats = await synth_data.apply(conn, batch, citizens, complaints, replace=False)

        rng = random.Random(99)
        demo = synth_data.PlannedCitizen(cid, uid, citizen_email, "Aarthi (demo citizen)", False, {})
        mine = []
        for i, (ref, title, scenario) in enumerate(DEMO_CITIZEN_COMPLAINTS):
            age_h = rng.randint(30, 20 * 24) if scenario != "overdue_open" else rng.randint(12 * 24, 30 * 24)
            created = synth_data.REFERENCE_TIME - timedelta(hours=age_h)
            path = synth_data.SCENARIOS[scenario]
            t, times = created, [created]
            for _ in path[1:]:
                t = t + timedelta(minutes=rng.randint(40, 60 * 16))
                times.append(t)
            mine.append(synth_data.PlannedComplaint(
                uuid.UUID(int=rng.getrandbits(128), version=4), ref, 0, cats[i % len(cats)], dists[i % len(dists)],
                title, scenario, created, path, times))
        stats_mine = await synth_data.apply(conn, "demo-citizen", [demo], mine, replace=False)
        out["synthetic_complaints_created"] = stats["complaints_created"] + stats_mine["complaints_created"]

        # --- assign officers to progressed synthetic complaints -----------------------------------
        rows = await conn.fetch(
            "SELECT complaint_id, complaint_ref, department_id FROM complaints.complaint "
            "WHERE is_synthetic AND assigned_officer_id IS NULL AND department_id IS NOT NULL "
            "AND status IN ('assigned','in_progress','escalated','resolved','closed','reopened')")
        assigned = 0
        for r in rows:
            pool = officers.get(r["department_id"])
            if pool:
                pick = pool[sum(map(ord, r["complaint_ref"])) % len(pool)]
                await conn.execute("UPDATE complaints.complaint SET assigned_officer_id=$2 WHERE complaint_id=$1", r["complaint_id"], pick)
                assigned += 1
        out["officer_assignments"] = assigned
        out["departments_with_officers"] = [d["department_name"] for d in depts]
        out["staff_departments"] = {"officer@" + DEMO_DOMAIN: depts[0]["department_name"], "officer2@" + DEMO_DOMAIN: depts[1]["department_name"],
                                    "deptadmin@" + DEMO_DOMAIN: depts[0]["department_name"]}
    finally:
        await conn.close()
    return out


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--admin-dsn", required=True, help="superuser DSN of a DISPOSABLE PostgreSQL server")
    ap.add_argument("--reset", action="store_true", help=f"drop and rebuild {DB}")
    ap.add_argument("--db", default=DB, help="database name (must match mygovt_dev*/mygovt_test*/mygovt_synth*)")
    args = ap.parse_args(argv)
    password = os.getenv("DEMO_PASSWORD", DEFAULT_PASSWORD)
    dsn = await build_database(args.admin_dsn, args.reset, args.db)
    synth_data.check_target(dsn)
    info = await populate(dsn, password)
    print(f"ready: {args.db}")
    for k, v in info.items():
        print(f"  {k}: {v}")
    print(f"  logins (password from DEMO_PASSWORD, default shown in docs/demo.md): citizen@{DEMO_DOMAIN}, officer@{DEMO_DOMAIN}, "
          f"officer2@{DEMO_DOMAIN}, deptadmin@{DEMO_DOMAIN}, admin@{DEMO_DOMAIN}, sysadmin@{DEMO_DOMAIN}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
