"""Synthetic data generator: determinism, safety, idempotence, isolation from official data."""
import hashlib

import asyncpg
import pytest

from app.services import complaint_rules as rules
from scripts import synth_data as sd

CATS = list(range(1, 11))
DISTS = list(range(1, 39))
OFFICIAL = {
    "schemes.scheme": "scheme_code, scheme_name, verification_status",
    "services.service": "service_code, service_name, verification_status",
    "administration.district": "district_code, district_name, lgd_code, verification_status",
    "administration.department": "department_code, department_name, verification_status",
    "system.source_registry": "source_code, source_type, url",
    "system.dataset_registry": "dataset_name, checksum_sha256",
    "complaints.complaint_category": "category_code",
    "complaints.sla_rule": "priority, resolution_hours",
    "administration.authority": "authority_name",
}


# -- pure plan (no DB) -----------------------------------------------------------------------
def test_plan_is_deterministic_and_seed_dependent():
    a = sd.plan(7, 20, 60, CATS, DISTS)
    b = sd.plan(7, 20, 60, CATS, DISTS)
    c = sd.plan(8, 20, 60, CATS, DISTS)
    assert a == b
    assert [x.citizen_id for x in a[1]] != [x.citizen_id for x in c[1]]
    assert a[0] == "synth-seed7"


def test_plan_shape_and_uniqueness():
    batch, cits, comps = sd.plan(1, 30, 120, CATS, DISTS)
    assert (len(cits), len(comps)) == (30, 120)
    assert len({c.email for c in cits}) == 30 and len({c.citizen_id for c in cits}) == 30
    assert len({k.ref for k in comps}) == 120 and len({k.complaint_id for k in comps}) == 120
    assert all(c.email.endswith("@synthetic.invalid") and c.name.startswith("Synthetic Citizen") for c in cits)
    assert all(k.category_id in CATS and k.district_id in DISTS for k in comps)


def test_every_planned_path_is_legal_and_times_monotonic():
    _, _, comps = sd.plan(3, 10, 400, CATS, DISTS)
    assert {k.scenario for k in comps} == set(sd.SCENARIOS)           # all scenarios are exercised
    for k in comps:
        assert all(rules.can_transition(a, b) for a, b in zip(k.path, k.path[1:], strict=False)), k.scenario
        assert k.step_times == sorted(k.step_times) and len(k.step_times) == len(k.path)


def test_plan_validates_counts():
    with pytest.raises(ValueError):
        sd.plan(1, 0, 5, CATS, DISTS)
    with pytest.raises(ValueError):
        sd.plan(1, -1, 0, CATS, DISTS)
    assert sd.plan(1, 0, 0, CATS, DISTS)[1:] == ([], [])


@pytest.mark.parametrize("dsn,ok", [
    ("postgresql://u@h/mygovt", False), ("postgresql://u@h/postgres", False), ("postgresql://u@h/mygovt_prod", False),
    ("postgresql://u@h/mygovt_testing_x", False), ("postgresql://u@h/prod_mygovt_test", False),
    ("postgresql://u@h/mygovt_test_ab12", True), ("postgresql://u@h/mygovt_dev", True), ("postgresql://u@h/mygovt_synth_1", True),
])
def test_target_database_guard(dsn, ok):
    if ok:
        sd.check_target(dsn)
    else:
        with pytest.raises(SystemExit):
            sd.check_target(dsn)


# -- database ---------------------------------------------------------------------------------
async def _official_fingerprint(conn):
    out = {}
    for table, cols in OFFICIAL.items():
        row = await conn.fetchrow(f"SELECT count(*) n, coalesce(md5(string_agg(t::text,'|' ORDER BY t::text)),'') h FROM (SELECT {cols} FROM {table}) t")
        out[table] = (row["n"], row["h"])
    return out


@pytest.fixture
async def fresh(test_db_dsn):
    """A dedicated connection; cleans this test's synthetic rows afterwards."""
    c = await asyncpg.connect(test_db_dsn)
    yield c
    await c.execute("DELETE FROM complaints.complaint WHERE is_synthetic")
    await c.execute("DELETE FROM identity.consent WHERE citizen_id IN (SELECT citizen_id FROM identity.citizen WHERE is_synthetic)")
    await c.execute("DELETE FROM identity.citizen_profile WHERE citizen_id IN (SELECT citizen_id FROM identity.citizen WHERE is_synthetic)")
    await c.execute("DELETE FROM identity.citizen WHERE is_synthetic")
    await c.execute("DELETE FROM identity.app_user WHERE is_synthetic")
    await c.close()


@pytest.mark.db
async def test_generation_labels_everything_and_leaves_official_data_untouched(fresh, test_db_dsn):
    before = await _official_fingerprint(fresh)
    assert await sd.main(["--dsn", test_db_dsn, "--seed", "11", "--citizens", "15", "--complaints", "60"]) == 0
    assert await _official_fingerprint(fresh) == before                       # isolation from official datasets

    assert await fresh.fetchval("SELECT count(*) FROM identity.citizen WHERE is_synthetic") == 15
    assert await fresh.fetchval("SELECT count(*) FROM complaints.complaint WHERE is_synthetic AND synthetic_batch='synth-seed11'") == 60
    # nothing synthetic is unlabelled, nothing unlabelled is synthetic-looking
    assert await fresh.fetchval("SELECT count(*) FROM identity.app_user WHERE email LIKE '%@synthetic.invalid' AND NOT is_synthetic") == 0
    assert await fresh.fetchval("SELECT count(*) FROM complaints.complaint c JOIN identity.citizen z USING (citizen_id) "
                                "WHERE c.is_synthetic <> z.is_synthetic") == 0
    assert await fresh.fetchval("SELECT count(*) FROM complaints.complaint WHERE is_synthetic AND title NOT LIKE '[SYNTHETIC]%'") == 0
    assert await fresh.fetchval("SELECT count(*) FROM system.source_registry WHERE source_type='synthetic'") == 0


@pytest.mark.db
async def test_rerun_is_idempotent_and_replace_regenerates_identically(fresh, test_db_dsn):
    args = ["--dsn", test_db_dsn, "--seed", "12", "--citizens", "8", "--complaints", "30"]
    await sd.main(args)

    async def snap():
        rows = await fresh.fetch("SELECT complaint_ref,status,priority,category_id,district_id,created_at,due_date,resolved_at FROM complaints.complaint WHERE is_synthetic ORDER BY complaint_ref")
        return hashlib.md5(repr([tuple(r) for r in rows]).encode()).hexdigest(), len(rows)

    first = await snap()
    await sd.main(args)                                                        # second run: all skipped
    assert await snap() == first
    await sd.main(args + ["--replace"])                                        # regenerated: identical content
    assert await snap() == first


@pytest.mark.db
async def test_dry_run_persists_nothing(fresh, test_db_dsn):
    assert await sd.main(["--dsn", test_db_dsn, "--seed", "13", "--citizens", "5", "--complaints", "10", "--dry-run"]) == 0
    assert await fresh.fetchval("SELECT count(*) FROM identity.citizen WHERE is_synthetic") == 0
    assert await fresh.fetchval("SELECT count(*) FROM complaints.complaint WHERE is_synthetic") == 0


@pytest.mark.db
async def test_replace_only_deletes_its_own_batch(fresh, test_db_dsn):
    await sd.main(["--dsn", test_db_dsn, "--seed", "14", "--citizens", "4", "--complaints", "8"])
    await sd.main(["--dsn", test_db_dsn, "--seed", "15", "--citizens", "4", "--complaints", "8"])
    await sd.main(["--dsn", test_db_dsn, "--seed", "14", "--citizens", "4", "--complaints", "8", "--replace"])
    batches = {r[0]: r[1] for r in await fresh.fetch("SELECT synthetic_batch, count(*) FROM complaints.complaint WHERE is_synthetic GROUP BY 1")}
    assert batches == {"synth-seed14": 8, "synth-seed15": 8}


@pytest.mark.db
async def test_histories_and_sla_scenarios_are_consistent(fresh, test_db_dsn):
    await sd.main(["--dsn", test_db_dsn, "--seed", "16", "--citizens", "20", "--complaints", "300"])
    comps = await fresh.fetch("SELECT complaint_id,status,created_at,due_date,resolved_at,department_id,authority_id FROM complaints.complaint WHERE is_synthetic")
    assert len(comps) == 300
    late = ontime = overdue = 0
    for c in comps:
        hist = await fresh.fetch("SELECT old_status,new_status,changed_at FROM complaints.complaint_history WHERE complaint_id=$1 ORDER BY history_id", c["complaint_id"])
        assert hist[-1]["new_status"] == c["status"]                           # history ends at current status
        assert all(rules.can_transition(h["old_status"], h["new_status"]) for h in hist[1:])
        assert [h["changed_at"] for h in hist] == sorted(h["changed_at"] for h in hist)
        assert hist[0]["changed_at"] == c["created_at"]
        assert c["department_id"] is not None and c["authority_id"] is not None   # routed via seeded routing targets
        if c["status"] in ("resolved", "closed"):
            assert c["resolved_at"] is not None
            late += c["resolved_at"] > c["due_date"]
            ontime += c["resolved_at"] <= c["due_date"]
        else:
            assert c["resolved_at"] is None
            overdue += c["due_date"] < sd.REFERENCE_TIME and c["status"] in ("in_progress", "assigned")
    assert late > 0 and ontime > 0 and overdue > 0                             # SLA scenarios actually present


@pytest.mark.db
async def test_synthetic_users_cannot_log_in(fresh, client, test_db_dsn, session_factory):
    from app.services.auth_service import AuthService

    await sd.main(["--dsn", test_db_dsn, "--seed", "17", "--citizens", "2", "--complaints", "0"])
    email = await fresh.fetchval("SELECT email FROM identity.app_user WHERE is_synthetic LIMIT 1")
    for pw in ("password", "Synthetic1234", "synthetic17-00001"):
        # layer 1: the API's e-mail validation rejects the reserved .invalid domain outright
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
        assert r.status_code in (401, 422)
        # layer 2: even bypassing the schema, the stored credential is unusable
        async with session_factory() as s:
            assert await AuthService(s).login(email, pw) is None


@pytest.mark.db
async def test_database_rejects_unlabelled_or_real_looking_synthetic_users(fresh):
    with pytest.raises(asyncpg.CheckViolationError):
        await fresh.execute("INSERT INTO identity.app_user (email,password_hash,role,is_synthetic) VALUES ('real.person@gmail.com','x','citizen',true)")


@pytest.mark.db
async def test_refuses_non_test_database_and_missing_seed(test_db_dsn):
    with pytest.raises(SystemExit):
        await sd.main(["--dsn", test_db_dsn.rsplit("/", 1)[0] + "/mygovt"])
