"""Apply the verified Tamil Nadu seed data and validate the result.

Usage (inside the backend container, or anywhere with asyncpg installed)::

    python -m scripts.seed                 # apply seed, then run checks
    python -m scripts.seed --dry-run       # apply + check inside a transaction, then roll back
    python -m scripts.seed --verify-only   # run checks only
    python -m scripts.seed --strict        # treat provenance WARNINGs as failures

Initialisation order (see ``make db-init``)::

    1. database/schema/001_schema.sql                      baseline schema
    2. database/migrations/002_provenance_and_audit_fixes.sql   provenance columns
    3. database/seeds/002_verified_seed_data.sql           THIS SCRIPT

Only ``002_verified_seed_data.sql`` is applied. ``001_seed_data.sql`` is a legacy
unaudited seed (30+ schemes with no provenance) and is deliberately NOT run.

The seed is idempotent: every INSERT uses ON CONFLICT ... DO UPDATE / DO NOTHING and
the UPDATE blocks set fixed values, so re-running leaves row counts unchanged.

Connection settings come from ``--dsn`` / ``SEED_DATABASE_URL`` or the same POSTGRES_*
variables used by the backend (``app.core.config``). No credentials are hard-coded.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import asyncpg

SEED_FILES = ["002_verified_seed_data.sql"]
PLACEHOLDER_CHECKSUMS = {
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # sha256 of empty input
    "a1b2c3d4" * 8,
    "f0e1d2c3" * 8,
}
VERIFIED = "official_verified"
# Higher = stronger claim of verification
STATUS_RANK = {"deprecated": 0, "unverified": 1, "provisional": 2, "externally_referenced": 3, "official_verified": 4}


# ── paths & connection ─────────────────────────────────────────────────────────
def _first_existing(candidates: list[Path]) -> Path | None:
    return next((c for c in candidates if c.is_dir()), None)


def seed_dir() -> Path:
    here = Path(__file__).resolve()
    env = os.getenv("SEED_DIR")
    found = _first_existing(
        ([Path(env)] if env else []) + [Path("/database/seeds"), here.parents[2] / "database" / "seeds"]
    )
    if not found:
        raise FileNotFoundError("seed directory not found; set SEED_DIR")
    return found


def data_dir() -> Path | None:
    """Directory holding the validated JSON datasets (optional; enables file checks)."""
    here = Path(__file__).resolve()
    env = os.getenv("VALIDATED_DATA_DIR")
    return _first_existing(
        ([Path(env)] if env else []) + [Path("/data/validated"), here.parents[2] / "data" / "validated"]
    )


def default_dsn() -> str:
    if os.getenv("SEED_DATABASE_URL"):
        return os.environ["SEED_DATABASE_URL"]
    g = os.getenv
    return "postgresql://{u}:{p}@{h}:{port}/{db}".format(
        u=quote(g("POSTGRES_USER", "postgres")),
        p=quote(g("POSTGRES_PASSWORD", "")),
        h=g("POSTGRES_HOST", "localhost"),
        port=g("POSTGRES_PORT", "5432"),
        db=g("POSTGRES_DB", "mygovt"),
    )


# ── results ────────────────────────────────────────────────────────────────────
@dataclass
class Check:
    name: str
    status: str  # PASS | FAIL | WARN
    detail: str = ""


# ── preflight / apply ──────────────────────────────────────────────────────────
async def preflight(conn: asyncpg.Connection) -> list[str]:
    """Return a list of problems that mean the schema/migrations were not applied."""
    problems: list[str] = []
    for table in ("administration.district", "schemes.scheme", "system.dataset_registry"):
        if await conn.fetchval("SELECT to_regclass($1)", table) is None:
            problems.append(f"table {table} missing - apply database/schema/001_schema.sql first")
    if problems:
        return problems
    needed = [
        ("administration", "district", "lgd_code"),
        ("administration", "department", "verification_status"),
        ("schemes", "scheme", "source_document_ref"),
        ("services", "service", "verification_status"),
        ("complaints", "sla_rule", "sla_source_type"),
        ("complaints", "complaint", "address"),
        ("administration", "district", "source_document_ref"),
    ]
    for schema, table, col in needed:
        ok = await conn.fetchval(
            "SELECT 1 FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2 AND column_name=$3",
            schema, table, col,
        )
        if not ok:
            problems.append(
                f"{schema}.{table}.{col} missing - apply the SQL files in database/migrations/ (002, 003, ...)"
            )
    return problems


async def apply_seed(conn: asyncpg.Connection) -> list[str]:
    applied = []
    base = seed_dir()
    for name in SEED_FILES:
        sql = (base / name).read_text(encoding="utf-8")
        await conn.execute(sql)  # simple-query protocol: multi-statement script
        applied.append(name)
    return applied


# ── checks ─────────────────────────────────────────────────────────────────────
EXPECTED_UNIQUE = [
    ("administration", "district", ["district_code"]),
    ("administration", "district", ["lgd_code"]),
    ("administration", "department", ["department_code"]),
    ("schemes", "scheme", ["scheme_code"]),
    ("system", "source_registry", ["source_code"]),
    ("system", "dataset_registry", ["source_id", "checksum_sha256"]),
]


async def _has_unique(conn: asyncpg.Connection, schema: str, table: str, cols: list[str]) -> bool:
    rows = await conn.fetch(
        """
        SELECT array_agg(a.attname::text ORDER BY k.ord) AS cols
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
        WHERE i.indisunique AND n.nspname = $1 AND c.relname = $2 AND i.indpred IS NULL
        GROUP BY i.indexrelid
        """,
        schema, table,
    )
    return any(sorted(r["cols"]) == sorted(cols) for r in rows)


def _load_json(base: Path | None, name: str):
    if base is None or not (base / name).is_file():
        return None
    return json.loads((base / name).read_text(encoding="utf-8"))


async def run_checks(conn: asyncpg.Connection) -> list[Check]:
    out: list[Check] = []
    add = lambda n, ok, d="", warn=False: out.append(  # noqa: E731
        Check(n, "PASS" if ok else ("WARN" if warn else "FAIL"), d)
    )
    ddir = data_dir()
    districts = _load_json(ddir, "tn_districts_master_2026.json")
    schemes = _load_json(ddir, "tn_schemes_verified_2026.json")
    services = _load_json(ddir, "tnega_esevai_services_2026.json")
    if ddir is None:
        out.append(Check("validated datasets present", "WARN", "data/validated not found; file-level checks skipped"))

    # constraints
    for schema, table, cols in EXPECTED_UNIQUE:
        add(f"unique constraint {schema}.{table}({', '.join(cols)})", await _has_unique(conn, schema, table, cols))

    # row counts vs validated datasets
    async def count(sql: str) -> int:
        return await conn.fetchval(sql)

    n_dist = await count("SELECT count(*) FROM administration.district")
    add("districts == 38", n_dist == 38, f"found {n_dist}")
    n_state = await count("SELECT count(*) FROM administration.state WHERE state_code='TN'")
    add("state TN present", n_state == 1, f"found {n_state}")
    if schemes is not None:
        n = await count("SELECT count(*) FROM schemes.scheme")
        add(f"schemes == {len(schemes)} (validated JSON)", n == len(schemes), f"found {n}")
    if services is not None:
        n = await count("SELECT count(*) FROM services.service")
        add(f"services == {len(services)} (validated JSON)", n == len(services), f"found {n}")

    # LGD codes
    n_lgd = await count("SELECT count(DISTINCT lgd_code) FROM administration.district WHERE lgd_code IS NOT NULL")
    add("all districts have a unique lgd_code", n_lgd == n_dist, f"{n_lgd} distinct of {n_dist}")
    if districts is not None:
        db = {r["district_code"]: r["lgd_code"] for r in await conn.fetch(
            "SELECT district_code, lgd_code FROM administration.district")}
        bad = [d["district_code"] for d in districts if db.get(d["district_code"]) != d["lgd_code"]]
        add("district LGD codes match validated JSON", not bad, f"mismatched: {bad}" if bad else "")

    # scheme source references vs JSON
    if schemes is not None:
        db = {r["scheme_code"]: r["source_document_ref"] for r in await conn.fetch(
            "SELECT scheme_code, source_document_ref FROM schemes.scheme")}
        bad = [s["scheme_code"] for s in schemes if db.get(s["scheme_code"]) != s["source_reference"]]
        add("scheme source refs match validated JSON", not bad, f"mismatched: {bad}" if bad else "")
        # The DB may be MORE cautious than the curated JSON, never more confident.
        db_status = {r["scheme_code"]: r["verification_status"] for r in await conn.fetch(
            "SELECT scheme_code, verification_status FROM schemes.scheme")}
        bad = [s["scheme_code"] for s in schemes
               if STATUS_RANK.get(db_status.get(s["scheme_code"]), -1) > STATUS_RANK.get(s["verification_status"], -1)]
        add("no scheme is more verified in the DB than in the validated JSON", not bad,
            f"over-claimed: {bad}" if bad else "")

    # dataset registry: checksum format, placeholders, on-disk match
    rows = await conn.fetch("SELECT file_name, checksum_sha256, record_count FROM system.dataset_registry")
    badfmt = [r["file_name"] for r in rows if not re.fullmatch(r"[0-9a-f]{64}", r["checksum_sha256"] or "")
              or r["checksum_sha256"] in PLACEHOLDER_CHECKSUMS]
    add("dataset checksums are well-formed, non-placeholder", not badfmt, f"bad: {badfmt}" if badfmt else "")
    if ddir is not None:
        mism = []
        for r in rows:
            f = ddir / (r["file_name"] or "")
            if f.is_file():
                if hashlib.sha256(f.read_bytes()).hexdigest() != r["checksum_sha256"]:
                    mism.append(r["file_name"])
        add("dataset checksums match files on disk", not mism, f"mismatch: {mism}" if mism else "")

    # serial sequences must sit past the explicit ids the seed inserted
    for schema, table, col in (("administration", "state", "state_id"),
                               ("administration", "district", "district_id"),
                               ("administration", "department", "department_id"),
                               ("complaints", "complaint_category", "category_id")):
        nxt = await conn.fetchval(
            f"SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END "
            f"FROM {schema}.{table}_{col}_seq"
        )
        mx = await count(f"SELECT coalesce(max({col}), 0) FROM {schema}.{table}")
        add(f"sequence {schema}.{table}_{col}_seq is past max id", nxt > mx, f"next={nxt} max={mx}")

    # source linkage + no synthetic data in verified tables
    n = await count("SELECT count(*) FROM schemes.scheme WHERE source_id IS NULL")
    add("every scheme has a source_id", n == 0, f"{n} without source")
    n = await count("SELECT count(*) FROM system.source_registry WHERE source_type='synthetic'")
    add("no synthetic sources in verified seed", n == 0, f"{n} synthetic sources")

    # verification governance (migration 004)
    tables = (("administration", "district"), ("administration", "department"), ("schemes", "scheme"),
              ("services", "service"), ("complaints", "complaint_category"))
    for schema, table in tables:
        cname = f"chk_{table}_verified_has_source"
        validated = await conn.fetchval(
            "SELECT convalidated FROM pg_constraint WHERE conname=$1 AND conrelid=$2::regclass",
            cname, f"{schema}.{table}")
        add(f"constraint {cname} exists and is validated", bool(validated),
            "missing" if validated is None else "not validated" if not validated else "")
        n = await count(
            f"SELECT count(*) FROM {schema}.{table} WHERE verification_status='{VERIFIED}' "
            "AND btrim(coalesce(source_document_ref,''))=''")
        add(f"provenance: every official_verified {schema}.{table} row has source_document_ref", n == 0, f"{n} lack one")
    for schema, table in (("administration", "department"), ("schemes", "scheme"), ("services", "service")):
        n = await count(
            f"SELECT count(*) FROM {schema}.{table} WHERE verification_status<>'{VERIFIED}' "
            "AND (verified_at IS NOT NULL OR verified_by IS NOT NULL)")
        add(f"{schema}.{table}: non-verified rows carry no verified_at/verified_by", n == 0, f"{n} rows claim verification")
    n_ver = sum([await count(f"SELECT count(*) FROM {s}.{t} WHERE verification_status='{VERIFIED}'") for s, t in tables])
    n_log = await count("SELECT count(*) FROM system.verification_status_log")
    add("verification_status_log records status writes", n_log > 0, f"{n_log} log rows")
    out.append(Check("official_verified records in database", "PASS",
                     f"{n_ver} (records are provisional until official evidence is recorded)"))
    return out


def print_report(checks: list[Check]) -> None:
    for c in checks:
        print(f"[{c.status:4}] {c.name}" + (f" - {c.detail}" if c.detail else ""))
    tally = {s: sum(c.status == s for c in checks) for s in ("PASS", "WARN", "FAIL")}
    print(f"\nsummary: {tally['PASS']} pass, {tally['WARN']} warn, {tally['FAIL']} fail")


# ── entry point ────────────────────────────────────────────────────────────────
async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", default=None, help="postgresql:// URL (default: SEED_DATABASE_URL or POSTGRES_*)")
    ap.add_argument("--dry-run", action="store_true", help="apply and check, then roll back")
    ap.add_argument("--verify-only", action="store_true", help="run checks without applying the seed")
    ap.add_argument("--strict", action="store_true", help="treat WARN as failure")
    args = ap.parse_args(argv)

    dsn = (args.dsn or default_dsn()).replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        problems = await preflight(conn)
        if problems:
            print("preflight FAILED:")
            for p in problems:
                print(f"  - {p}")
            return 2
        tx = conn.transaction()
        await tx.start()
        try:
            if not args.verify_only:
                for name in await apply_seed(conn):
                    print(f"applied {name}")
            checks = await run_checks(conn)
        except Exception:
            await tx.rollback()
            raise
        if args.dry_run or args.verify_only:
            await tx.rollback()
            if args.dry_run:
                print("dry-run: rolled back")
        else:
            failed = any(c.status == "FAIL" or (args.strict and c.status == "WARN") for c in checks)
            if failed:
                await tx.rollback()
                print("checks failed: seed rolled back")
            else:
                await tx.commit()
        print_report(checks)
        bad = any(c.status == "FAIL" or (args.strict and c.status == "WARN") for c in checks)
        return 1 if bad else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
