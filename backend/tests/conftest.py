"""Shared pytest fixtures.

Database tests need a DISPOSABLE PostgreSQL server: set ``TEST_ADMIN_DSN`` to a superuser DSN
(e.g. ``postgresql://postgres@localhost:5432/postgres``). A fresh ``mygovt_test_<random>``
database is created for the session and dropped afterwards. Without the variable those tests
are skipped (never run against the developer's ``mygovt`` database).

If the server lacks PostGIS the schema is loaded with spatial objects stubbed (see
``scripts.db_verify``); tests marked ``postgis`` are then skipped with an explicit reason.
"""
from __future__ import annotations

import os
import secrets
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
import pytest_asyncio

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-0123456789abcdef")

from scripts import db_verify, seed  # noqa: E402


def _with_db(dsn: str, db: str) -> str:
    return urlunsplit(urlsplit(dsn)._replace(path=f"/{db}"))


def pytest_configure(config):
    config.addinivalue_line("markers", "postgis: needs a real PostGIS-enabled database")
    config.addinivalue_line("markers", "db: needs TEST_ADMIN_DSN (disposable PostgreSQL)")


@pytest.fixture(scope="session")
def admin_dsn() -> str:
    dsn = os.getenv("TEST_ADMIN_DSN")
    if not dsn:
        pytest.skip("TEST_ADMIN_DSN not set - database tests need a disposable PostgreSQL server")
    return dsn


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def has_postgis(admin_dsn) -> bool:
    c = await asyncpg.connect(admin_dsn)
    try:
        return bool(await c.fetchval("SELECT 1 FROM pg_available_extensions WHERE name='postgis'"))
    finally:
        await c.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_db_dsn(admin_dsn, has_postgis):
    """Schema + migration 002 + verified seed in a throw-away database."""
    name = f"mygovt_test_{secrets.token_hex(4)}"
    assert name.startswith("mygovt_test_")
    admin = await asyncpg.connect(admin_dsn)
    await admin.execute(f'CREATE DATABASE "{name}"')
    dsn = _with_db(admin_dsn, name)
    conn = await asyncpg.connect(dsn)
    try:
        schema_sql = db_verify.SCHEMA.read_text(encoding="utf-8")
        if not has_postgis:
            await conn.execute(db_verify.POSTGIS_STUBS)
            schema_sql = db_verify.strip_postgis(schema_sql)
        await conn.execute(schema_sql)
        for mig in db_verify.MIGRATIONS:
            if not has_postgis and "postgis" in mig.name:
                continue  # spatial migration needs the real extension
            await conn.execute(mig.read_text(encoding="utf-8"))
        await seed.apply_seed(conn)
    finally:
        await conn.close()
    try:
        yield dsn
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()


@pytest_asyncio.fixture(loop_scope="session")
async def conn(test_db_dsn):
    c = await asyncpg.connect(test_db_dsn)
    try:
        yield c
    finally:
        await c.close()


def pytest_collection_modifyitems(config, items):
    # postgis-marked tests are blocked (not silently passed) unless a PostGIS server is configured.
    if os.getenv("TEST_POSTGIS") == "1":
        return
    skip = pytest.mark.skip(reason="BLOCKED: needs real PostGIS (set TEST_POSTGIS=1 with a PostGIS server)")
    for item in items:
        if "postgis" in item.keywords:
            item.add_marker(skip)
