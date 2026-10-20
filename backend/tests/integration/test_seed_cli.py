"""seed.py command-line behaviour (dry-run, verify-only, strict, preflight) and the public stats endpoint."""
import uuid

import asyncpg
import pytest

from scripts import db_verify, seed

pytestmark = pytest.mark.db


async def _fresh_db(admin_dsn, has_postgis, *, migrations=True, seeded=False):
    name = f"mygovt_test_seedcli_{uuid.uuid4().hex[:6]}"
    admin = await asyncpg.connect(admin_dsn)
    await admin.execute(f'CREATE DATABASE "{name}"')
    dsn = db_verify.with_db(admin_dsn, name)
    c = await asyncpg.connect(dsn)
    try:
        sql = db_verify.SCHEMA.read_text(encoding="utf-8")
        if not has_postgis:
            await c.execute(db_verify.POSTGIS_STUBS)
            sql = db_verify.strip_postgis(sql)
        await c.execute(sql)
        if migrations:
            for m in db_verify.MIGRATIONS:
                if not has_postgis and "postgis" in m.name:
                    continue
                await c.execute(m.read_text(encoding="utf-8"))
        if seeded:
            await seed.apply_seed(c)
    finally:
        await c.close()
    return admin, name, dsn


async def _drop(admin, name):
    await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    await admin.close()


async def _count(dsn, table="administration.district"):
    c = await asyncpg.connect(dsn)
    try:
        return await c.fetchval(f"SELECT count(*) FROM {table}")
    finally:
        await c.close()


async def test_apply_persists_and_exits_zero(admin_dsn, has_postgis, capsys):
    admin, name, dsn = await _fresh_db(admin_dsn, has_postgis)
    try:
        assert await seed.main(["--dsn", dsn]) == 0
        assert await _count(dsn) == 38 and "applied 002_verified_seed_data.sql" in capsys.readouterr().out
        assert await seed.main(["--dsn", dsn]) == 0                       # repeat run is safe
        assert await _count(dsn) == 38
    finally:
        await _drop(admin, name)


async def test_dry_run_checks_but_persists_nothing(admin_dsn, has_postgis, capsys):
    admin, name, dsn = await _fresh_db(admin_dsn, has_postgis)
    try:
        assert await seed.main(["--dsn", dsn, "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "dry-run: rolled back" in out and "0 fail" in out
        assert await _count(dsn) == 0
        assert await _count(dsn, "schemes.scheme") == 0
    finally:
        await _drop(admin, name)


async def test_verify_only_reports_discrepancies_without_repairing_them(admin_dsn, has_postgis, capsys):
    admin, name, dsn = await _fresh_db(admin_dsn, has_postgis, seeded=True)
    try:
        c = await asyncpg.connect(dsn)
        await c.execute("UPDATE administration.district SET lgd_code = NULL WHERE district_code = 'TN-CHN'")
        await c.close()
        assert await seed.main(["--dsn", dsn, "--verify-only"]) == 1       # discrepancy -> failure exit code
        out = capsys.readouterr().out
        assert "[FAIL] all districts have a unique lgd_code" in out and "[FAIL] district LGD codes match validated JSON" in out
        c = await asyncpg.connect(dsn)                                     # ...and it did NOT silently repair the row
        assert await c.fetchval("SELECT lgd_code FROM administration.district WHERE district_code='TN-CHN'") is None
        await c.close()
    finally:
        await _drop(admin, name)


async def test_failed_checks_roll_the_seed_back(admin_dsn, has_postgis, capsys, monkeypatch):
    admin, name, dsn = await _fresh_db(admin_dsn, has_postgis)
    try:
        async def failing_checks(conn):
            return [seed.Check("forced failure", "FAIL", "test")]

        monkeypatch.setattr(seed, "run_checks", failing_checks)
        assert await seed.main(["--dsn", dsn]) == 1
        assert "seed rolled back" in capsys.readouterr().out
        assert await _count(dsn) == 0
    finally:
        await _drop(admin, name)


async def test_strict_turns_warnings_into_failures(admin_dsn, has_postgis, capsys, monkeypatch):
    admin, name, dsn = await _fresh_db(admin_dsn, has_postgis)
    try:
        async def warn_only(conn):
            return [seed.Check("provenance gap", "WARN", "x")]

        monkeypatch.setattr(seed, "run_checks", warn_only)
        assert await seed.main(["--dsn", dsn, "--dry-run"]) == 0           # WARN alone is not a failure
        assert await seed.main(["--dsn", dsn, "--dry-run", "--strict"]) == 1
    finally:
        await _drop(admin, name)


async def test_preflight_refuses_unmigrated_and_empty_databases_with_exit_2(admin_dsn, has_postgis, capsys):
    admin, name, dsn = await _fresh_db(admin_dsn, has_postgis, migrations=False)     # schema only, no migrations
    try:
        assert await seed.main(["--dsn", dsn]) == 2
        out = capsys.readouterr().out
        assert "preflight FAILED" in out and "migrations" in out and await _count(dsn) == 0
    finally:
        await _drop(admin, name)
    a2 = await asyncpg.connect(admin_dsn)
    empty = f"mygovt_test_empty_{uuid.uuid4().hex[:6]}"
    await a2.execute(f'CREATE DATABASE "{empty}"')
    try:
        assert await seed.main(["--dsn", db_verify.with_db(admin_dsn, empty)]) == 2
        assert "001_schema.sql" in capsys.readouterr().out
    finally:
        await _drop(a2, empty)


async def test_failed_initialisation_surfaces_the_real_error(admin_dsn, has_postgis, monkeypatch):
    admin, name, dsn = await _fresh_db(admin_dsn, has_postgis)
    try:
        async def broken_apply(conn):
            await conn.execute("SELECT * FROM table_that_does_not_exist")

        monkeypatch.setattr(seed, "apply_seed", broken_apply)
        with pytest.raises(asyncpg.UndefinedTableError, match="table_that_does_not_exist"):
            await seed.main(["--dsn", dsn])
        assert await _count(dsn) == 0                                      # nothing half-applied
    finally:
        await _drop(admin, name)


async def test_legacy_seed_is_not_part_of_the_applied_set():
    assert seed.SEED_FILES == ["002_verified_seed_data.sql", "003_content.sql"]   # the legacy 001 seed is never applied
    assert not any("001_seed" in f for f in seed.SEED_FILES)


async def test_public_stats_are_live_counts_and_expose_no_personal_data(client, conn):
    body = (await client.get("/api/v1/public/stats")).json()
    assert set(body) == {"schemes", "services", "departments", "districts", "verified_schemes"}
    assert body["schemes"] == await conn.fetchval("SELECT count(*) FROM schemes.scheme WHERE status='active'")
    assert body["districts"] == 38 and body["verified_schemes"] == 0         # nothing is officially verified
