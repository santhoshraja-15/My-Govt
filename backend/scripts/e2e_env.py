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
        for email, role in (("e2e-admin@example.com", "state_admin"), ("e2e-sysadmin@example.com", "system_admin"), ("e2e-officer@example.com", "officer")):
            await conn.execute("INSERT INTO identity.app_user (email,password_hash,role) VALUES ($1,$2,$3)",
                               email, hash_password(password), role)
    finally:
        await conn.close()
    print(f"ready: {DB}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
