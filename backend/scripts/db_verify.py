"""Verify the database initialisation workflow against a DISPOSABLE database.

Creates ``mygovt_test_<random>`` on the server given by ``--admin-dsn``, then:

    1. applies database/schema/001_schema.sql
    2. applies every database/migrations/NNN_*.sql in order (each twice - must be idempotent)
    3. runs scripts.seed (apply + checks)
    4. runs the seed a second time and compares table fingerprints (idempotency)
    5. probes constraints with statements that MUST be rejected
    6. drops the database

It refuses to touch any database whose name does not start with ``mygovt_test_``.

``--no-postgis`` is for servers without the PostGIS extension (e.g. a plain local Postgres):
geometry columns are rewritten to ``text``, GIST indexes on them are dropped and three
``ST_*`` stubs are installed. That mode validates relational structure, constraints and
seed data ONLY - spatial behaviour (resolve_jurisdiction, location trigger) is NOT verified.
Use the real ``postgis/postgis`` image (``make db-verify``) for full coverage.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from scripts import seed

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "database" / "schema" / "001_schema.sql"
MIGRATIONS = sorted((REPO / "database" / "migrations").glob("[0-9][0-9][0-9]_*.sql"))

POSTGIS_STUBS = """
CREATE FUNCTION public.st_point(float8, float8) RETURNS text LANGUAGE sql IMMUTABLE AS 'SELECT NULL::text';
CREATE FUNCTION public.st_setsrid(text, int)    RETURNS text LANGUAGE sql IMMUTABLE AS 'SELECT $1';
CREATE FUNCTION public.st_contains(text, text)  RETURNS boolean LANGUAGE sql IMMUTABLE AS 'SELECT false';
"""

FINGERPRINT_TABLES = {
    "system.source_registry": "source_code, source_name, url, source_type, status",
    "administration.state": "state_code, state_name",
    "administration.district": "district_code, district_name, name_ta, headquarters, lgd_code, verification_status",
    "administration.department": "department_code, department_name, verification_status",
    "complaints.complaint_category": "category_code, verification_status",
    "complaints.sla_rule": "priority, sla_source_type",
    "schemes.scheme": "scheme_code, scheme_name, verification_status, funding_pattern, source_document_ref",
    "services.service": "service_code, verification_status",
    "system.dataset_registry": "dataset_name, checksum_sha256, record_count",
}

# (description, SQL, expected asyncpg exception class name; None = must succeed)
NEGATIVE_PROBES = [
    ("duplicate lgd_code rejected",
     "UPDATE administration.district SET lgd_code = (SELECT lgd_code FROM administration.district WHERE district_code='TN-CHN') "
     "WHERE district_code='TN-CBE'", "UniqueViolationError"),
    ("invalid verification_status rejected",
     "UPDATE schemes.scheme SET verification_status='made_up' WHERE scheme_code='TN-CM-BREAKFAST'", "CheckViolationError"),
    ("duplicate scheme_code rejected",
     "INSERT INTO schemes.scheme (scheme_code, scheme_name, department_id, state_id, scheme_level, category) "
     "SELECT scheme_code, 'dup', department_id, state_id, scheme_level, category FROM schemes.scheme LIMIT 1",
     "UniqueViolationError"),
    ("district with unknown state rejected",
     "INSERT INTO administration.district (district_id, state_id, district_code, district_name) VALUES (900, 999,'TN-ZZZ','x')",
     "ForeignKeyViolationError"),
    ("new district without explicit id gets a free serial id (sequence advanced)",
     "INSERT INTO administration.district (state_id, district_code, district_name) VALUES (1,'TN-ZZ2','probe')",
     None),
    ("dataset with unknown source rejected",
     "INSERT INTO system.dataset_registry (dataset_name, source_id, checksum_sha256) "
     "VALUES ('x', gen_random_uuid(), repeat('0',64))", "ForeignKeyViolationError"),
]


def strip_postgis(sql: str) -> str:
    sql = re.sub(r"^CREATE EXTENSION IF NOT EXISTS postgis;.*$", "", sql, flags=re.M)
    sql = re.sub(r"geometry\((?:Multi)?(?:Polygon|Point),4326\)", "text", sql)
    return re.sub(r"^CREATE INDEX .* USING GIST \((?:geometry|location)\);.*$", "", sql, flags=re.M)


def with_db(dsn: str, db: str) -> str:
    p = urlsplit(dsn)
    return urlunsplit(p._replace(path=f"/{db}"))


class _Rollback(Exception):
    pass


async def fingerprint(conn: asyncpg.Connection) -> dict[str, tuple[int, str]]:
    out = {}
    for table, cols in FINGERPRINT_TABLES.items():
        row = await conn.fetchrow(
            f"SELECT count(*) AS n, coalesce(md5(string_agg(t::text, '|' ORDER BY t::text)), '') AS h "
            f"FROM (SELECT {cols} FROM {table}) t"
        )
        out[table] = (row["n"], row["h"])
    return out


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--admin-dsn", required=True, help="superuser DSN of a DISPOSABLE server, e.g. postgresql://postgres@localhost:5432/postgres")
    ap.add_argument("--no-postgis", action="store_true", help="server lacks PostGIS; see module docstring")
    ap.add_argument("--keep", action="store_true", help="do not drop the test database afterwards")
    args = ap.parse_args()

    name = f"mygovt_test_{secrets.token_hex(4)}"
    assert name.startswith("mygovt_test_")
    admin = await asyncpg.connect(args.admin_dsn)
    failures = 0

    def step(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))

    await admin.execute(f'CREATE DATABASE "{name}"')
    print(f"created disposable database {name}")
    conn = await asyncpg.connect(with_db(args.admin_dsn, name))
    try:
        # 1. schema
        schema_sql = SCHEMA.read_text(encoding="utf-8")
        if args.no_postgis:
            print("NOTE: --no-postgis: spatial objects stubbed; spatial behaviour NOT verified")
            await conn.execute(POSTGIS_STUBS)
            schema_sql = strip_postgis(schema_sql)
        await conn.execute(schema_sql)
        step("001_schema.sql applies to a clean database", True)

        # 2. migration (twice)
        for mig_file in MIGRATIONS:
            mig = mig_file.read_text(encoding="utf-8")
            await conn.execute(mig)
            await conn.execute(mig)
            step(f"{mig_file.name} applies, and re-applies without error", True)

        # preflight must fail on a schema without the migration -> checked via seed preflight passing now
        problems = await seed.preflight(conn)
        step("seed preflight passes after migrations", not problems, "; ".join(problems))

        # 3. seed + checks
        await seed.apply_seed(conn)
        checks = await seed.run_checks(conn)
        seed.print_report(checks)
        step("seed applied; no FAIL checks", all(c.status != "FAIL" for c in checks))
        before = await fingerprint(conn)

        # 4. idempotency
        await seed.apply_seed(conn)
        after = await fingerprint(conn)
        diff = [t for t in before if before[t] != after[t]]
        step("re-running the seed is idempotent (counts + content unchanged)", not diff, f"changed: {diff}" if diff else "")

        # 5. negative probes
        for desc, sql, exc in NEGATIVE_PROBES:
            try:
                async with conn.transaction():
                    await conn.execute(sql)
                    if exc is None:  # must succeed; roll back so fingerprints stay clean
                        step(desc, True)
                        raise _Rollback
                step(desc, False, "statement was ACCEPTED")
            except _Rollback:
                pass
            except asyncpg.PostgresError as e:
                step(desc, type(e).__name__ == exc, f"raised {type(e).__name__}")

        # preflight negative: a DB without migration 002 must be refused
        bare = f"{name}_bare"
        await admin.execute(f'CREATE DATABASE "{bare}"')
        c2 = await asyncpg.connect(with_db(args.admin_dsn, bare))
        try:
            if args.no_postgis:
                await c2.execute(POSTGIS_STUBS)
            await c2.execute(schema_sql)
            problems = await seed.preflight(c2)
            step("seed preflight refuses a schema without migration 002", bool(problems), problems[0] if problems else "")
        finally:
            await c2.close()
            await admin.execute(f'DROP DATABASE IF EXISTS "{bare}"')
    finally:
        await conn.close()
        if not args.keep:
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            print(f"dropped {name}")
        await admin.close()

    print(f"\nresult: {'FAILED' if failures else 'OK'} ({failures} failing step(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
