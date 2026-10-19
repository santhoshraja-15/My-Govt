"""scripts.demo_env: builds a labelled, idempotent demo database without touching official records."""
import secrets

import asyncpg
import pytest

from app.security.jwt import verify_password
from scripts import db_verify, demo_env

pytestmark = [pytest.mark.db, pytest.mark.postgis]


async def test_demo_environment_is_complete_idempotent_and_labelled(admin_dsn):
    name = f"mygovt_dev_demotest_{secrets.token_hex(3)}"          # never the real demo database
    admin = await asyncpg.connect(admin_dsn)
    try:
        dsn = await demo_env.build_database(admin_dsn, reset=True, db=name)
        first = await demo_env.populate(dsn, demo_env.DEFAULT_PASSWORD)
        second = await demo_env.populate(dsn, demo_env.DEFAULT_PASSWORD)
        assert first["synthetic_complaints_created"] > 50 and first["officer_assignments"] > 0
        assert second["synthetic_complaints_created"] == 0 and second["officer_assignments"] == 0   # idempotent

        c = await asyncpg.connect(dsn)
        try:
            # every login exists with the right role; staff are linked to a department, others are not
            users = {r["email"]: r for r in await c.fetch(
                "SELECT u.email, u.role, o.department_id FROM identity.app_user u "
                "LEFT JOIN administration.officer o ON o.officer_id = u.officer_id WHERE u.email LIKE '%@demo.example'")}
            assert {e: users[e]["role"] for e in users} == {
                "citizen@demo.example": "citizen", "officer@demo.example": "officer", "officer2@demo.example": "officer",
                "deptadmin@demo.example": "department_admin", "admin@demo.example": "state_admin",
                "sysadmin@demo.example": "system_admin"}
            assert users["officer@demo.example"]["department_id"] and users["officer@demo.example"]["department_id"] != users["officer2@demo.example"]["department_id"]
            assert users["admin@demo.example"]["department_id"] is None
            h = await c.fetchval("SELECT password_hash FROM identity.app_user WHERE email='officer@demo.example'")
            assert verify_password(demo_env.DEFAULT_PASSWORD, h)

            # lifecycle coverage, labelled synthetic, with the demo citizen owning several
            statuses = {r[0] for r in await c.fetch("SELECT DISTINCT status FROM complaints.complaint")}
            assert {"classified", "in_progress", "escalated", "resolved", "closed"} <= statuses
            assert await c.fetchval("SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic") == 0
            assert await c.fetchval("SELECT bool_and(title LIKE '[SYNTHETIC]%') FROM complaints.complaint")
            mine = await c.fetchval(
                "SELECT count(*) FROM complaints.complaint k JOIN identity.citizen z ON z.citizen_id=k.citizen_id "
                "JOIN identity.app_user u ON u.user_id=z.user_id WHERE u.email='citizen@demo.example'")
            assert mine == 6
            # complaint histories follow the state machine (trigger-written, no duplicates)
            assert await c.fetchval(
                "SELECT count(*) FROM (SELECT complaint_id FROM complaints.complaint_history GROUP BY complaint_id, new_status "
                "HAVING count(*) > 1) d") == 0

            # demo rules are labelled and the official data is untouched (still provisional, none verified)
            assert await c.fetchval("SELECT count(*) FROM schemes.eligibility_rule WHERE human_readable NOT LIKE '[DEMO RULE]%'") == 0
            assert await c.fetchval("SELECT count(*) FROM schemes.eligibility_rule WHERE source_reference NOT LIKE 'DEMO RULE%'") == 0
            assert await c.fetchval("SELECT count(*) FROM schemes.scheme WHERE verification_status = 'official_verified'") == 0
        finally:
            await c.close()
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()


def test_demo_database_name_is_accepted_by_the_synthetic_data_guard():
    from scripts import synth_data
    assert synth_data.check_target(db_verify.with_db("postgresql://u@h/x", demo_env.DB)) == demo_env.DB
