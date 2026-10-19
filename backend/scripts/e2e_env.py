"""Create a DISPOSABLE database for the Playwright E2E suite: schema + migrations + seed + test users.

    python -m scripts.e2e_env --admin-dsn postgresql://postgres@localhost:5432/postgres

Creates (dropping any previous copy) the database ``mygovt_test_e2e`` and three staff accounts whose
credentials are TEST FIXTURES for that throw-away database only:
    e2e-admin@example.com   state_admin     password from E2E_ADMIN_PASSWORD (default below)
    e2e-officer@example.com officer         same password
Never run against a real server's data: the database name is fixed and test-prefixed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg

from scripts import db_verify, seed
from app.security.jwt import hash_password

DB = "mygovt_test_e2e"
DEFAULT_PASSWORD = "E2e-test-pass-1"     # fixture credential for the disposable E2E database only


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-dsn", required=True)
    ap.add_argument("--no-postgis", action="store_true")
    args = ap.parse_args()
    password = os.getenv("E2E_ADMIN_PASSWORD", DEFAULT_PASSWORD)

    admin = await asyncpg.connect(args.admin_dsn)
    await admin.execute(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
    await admin.execute(f'CREATE DATABASE "{DB}"')
    await admin.close()
    conn = await asyncpg.connect(db_verify.with_db(args.admin_dsn, DB))
    try:
        sql = db_verify.SCHEMA.read_text(encoding="utf-8")
        if args.no_postgis:
            await conn.execute(db_verify.POSTGIS_STUBS)
            sql = db_verify.strip_postgis(sql)
        await conn.execute(sql)
        for m in db_verify.MIGRATIONS:
            if args.no_postgis and "postgis" in m.name:
                continue
            await conn.execute(m.read_text(encoding="utf-8"))
        await seed.apply_seed(conn)
        # One clearly-labelled FIXTURE document so the UI's document-citation path can be tested end to end.
        # It is not an official document: title says so, it has no source URL and stays 'unverified'.
        did = await conn.fetchval(
            "INSERT INTO documents.document (title,document_type,file_hash,status,extraction_status,verification_status,retrieved_at,page_count) "
            "VALUES ('[E2E TEST FIXTURE] Zorblax scholarship notice','Notice','e2e-fixture-1','active','ok','unverified',now(),2) RETURNING document_id")
        await conn.execute(
            "INSERT INTO documents.document_chunk (document_id,chunk_number,content,page_number) VALUES ($1,0,$2,2)", did,
            "The Zorblax scholarship test notice describes a fictional monthly grant used only by automated tests.")
        for email, role in (("e2e-admin@example.com", "state_admin"), ("e2e-sysadmin@example.com", "system_admin")):
            await conn.execute("INSERT INTO identity.app_user (email,password_hash,role) VALUES ($1,$2,$3)",
                               email, hash_password(password), role)
        # Officers belong to a department: officer #1 to the department of the FIRST complaint category by name (the one the
        # E2E specs file against), officer #2 to a different department (used to prove department scoping).
        depts = [r["default_department_id"] for r in await conn.fetch(
            "SELECT DISTINCT ON (default_department_id) default_department_id, min(category_name) OVER (PARTITION BY default_department_id) AS n "
            "FROM complaints.complaint_category WHERE is_active AND default_department_id IS NOT NULL ORDER BY default_department_id, n")]
        first_dept = await conn.fetchval(
            "SELECT default_department_id FROM complaints.complaint_category WHERE is_active ORDER BY category_name LIMIT 1")
        other_dept = next(d for d in depts if d != first_dept)
        for email, dept, label in (("e2e-officer@example.com", first_dept, "E2E Officer"), ("e2e-officer2@example.com", other_dept, "E2E Officer Two")):
            authority = await conn.fetchval(
                "SELECT authority_id FROM administration.authority WHERE department_id=$1 ORDER BY authority_id LIMIT 1", dept)
            oid = await conn.fetchval(
                "INSERT INTO administration.officer (department_id,authority_id,name,designation,status) "
                "VALUES ($1,$2,$3,'Test Officer (E2E fixture)','active') RETURNING officer_id", dept, authority, label)
            await conn.execute("INSERT INTO identity.app_user (email,password_hash,role,officer_id) VALUES ($1,$2,'officer',$3)",
                               email, hash_password(password), oid)
    finally:
        await conn.close()
    print(f"ready: {DB}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
