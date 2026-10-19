"""Generate clearly-labelled SYNTHETIC citizens and complaints for development and load testing.

    python -m scripts.synth_data --dsn postgresql://.../mygovt_dev --seed 42 --citizens 50 --complaints 200
    python -m scripts.synth_data --dry-run ...     # plan + validate, persist nothing
    python -m scripts.synth_data --replace ...     # delete this seed's synthetic rows first

Guarantees
* Only databases named mygovt_test*, mygovt_dev* or mygovt_synth* are accepted; anything else
  (including the default ``mygovt`` database) is refused.
* Every row is flagged ``is_synthetic`` with a ``synthetic_batch`` label. Synthetic users use the
  reserved ``@synthetic.invalid`` domain and an unusable password. No real names, phone numbers or
  addresses are generated. Official tables (schemes, services, departments, districts, sources,
  datasets) are never written.
* Deterministic: the same ``--seed`` and counts produce byte-identical records (ids, references,
  timestamps are derived from the seed and a fixed reference time), so re-running is idempotent
  (existing rows are skipped; ``--replace`` regenerates them).
* Complaint histories follow the real state machine (app.services.complaint_rules) and routing /
  SLA come from the seeded routing_rule / sla_rule tables.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import re
import secrets
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import asyncpg

from app.services import complaint_rules as rules

ALLOWED_DB = re.compile(r"^mygovt_(test|dev|synth)(_\w*)?$")
REFERENCE_TIME = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)   # fixed => deterministic output
SYNTH_DOMAIN = "synthetic.invalid"

GENDERS = ["female", "male", "transgender", "other", "undisclosed"]
CATEGORIES = ["BC", "MBC", "SC", "ST", "OC"]
OCCUPATIONS = ["farmer", "student", "daily wage worker", "homemaker", "self-employed", "unemployed"]
TITLES = [
    "Streetlight not working", "Irregular drinking water supply", "Pothole on main road",
    "Garbage not collected", "Delay in certificate issue", "Pension not credited",
    "School toilet needs repair", "Drain overflow near market",
]
BODY = "This is a SYNTHETIC test complaint generated for development; it describes no real incident."

# Terminal scenarios and the status paths that reach them (all legal per TRANSITIONS).
SCENARIOS = {
    "open_new":        ["submitted", "classified"],
    "in_progress":     ["submitted", "classified", "assigned", "in_progress"],
    "resolved_on_time": ["submitted", "classified", "assigned", "in_progress", "resolved"],
    "resolved_late":   ["submitted", "classified", "assigned", "in_progress", "resolved"],
    "closed":          ["submitted", "classified", "assigned", "in_progress", "resolved", "closed"],
    "escalated":       ["submitted", "classified", "assigned", "in_progress", "escalated"],
    "rejected":        ["submitted", "rejected"],
    "overdue_open":    ["submitted", "classified", "assigned", "in_progress"],   # past SLA, not resolved
}
SCENARIO_WEIGHTS = {"open_new": 10, "in_progress": 20, "resolved_on_time": 25, "resolved_late": 8,
                    "closed": 15, "escalated": 8, "rejected": 4, "overdue_open": 10}


@dataclass
class PlannedCitizen:
    citizen_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    name: str
    has_profile: bool
    profile: dict = field(default_factory=dict)


@dataclass
class PlannedComplaint:
    complaint_id: uuid.UUID
    ref: str
    citizen_index: int
    category_id: int
    district_id: int
    title: str
    scenario: str
    created_at: datetime
    path: list[str]
    step_times: list[datetime]


def _uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def plan(seed: int, n_citizens: int, n_complaints: int, category_ids: list[int], district_ids: list[int]):
    """Pure, deterministic generation of what would be written (no I/O)."""
    if n_citizens < 0 or n_complaints < 0:
        raise ValueError("counts must be >= 0")
    if n_complaints and not n_citizens:
        raise ValueError("complaints need at least one citizen")
    rng = random.Random(seed)
    batch = f"synth-seed{seed}"
    citizens = []
    for i in range(1, n_citizens + 1):
        has_profile = rng.random() < 0.5
        profile = {}
        if has_profile:
            profile = {
                "gender": rng.choice(GENDERS), "occupation": rng.choice(OCCUPATIONS),
                "annual_income": rng.choice([60000, 120000, 240000, 480000, 900000]),
                "social_category": rng.choice(CATEGORIES),
                "residence_type": rng.choice(["rural", "urban"]),
                "district_id": rng.choice(district_ids), "family_size": rng.randint(1, 8),
                "is_student": rng.random() < 0.2, "bpl_status": rng.random() < 0.3,
                "disability_status": rng.random() < 0.08,
            }
        citizens.append(PlannedCitizen(_uuid(rng), _uuid(rng), f"synthetic{seed}-{i:05d}@{SYNTH_DOMAIN}",
                                       f"Synthetic Citizen {seed}-{i:05d}", has_profile, profile))
    names = list(SCENARIO_WEIGHTS)
    weights = [SCENARIO_WEIGHTS[n] for n in names]
    complaints = []
    for i in range(1, n_complaints + 1):
        scenario = rng.choices(names, weights)[0]
        age_h = rng.randint(6, 90 * 24) if scenario != "overdue_open" else rng.randint(10 * 24, 90 * 24)
        created = REFERENCE_TIME - timedelta(hours=age_h)
        path = SCENARIOS[scenario]
        t, times = created, [created]
        for _ in path[1:]:
            t = t + timedelta(minutes=rng.randint(20, 60 * 20))
            times.append(t)
        complaints.append(PlannedComplaint(
            _uuid(rng), f"SYN-{seed}-{i:06d}", rng.randrange(n_citizens), rng.choice(category_ids),
            rng.choice(district_ids), rng.choice(TITLES), scenario, created, path, times))
    return batch, citizens, complaints


def check_target(dsn: str) -> str:
    name = urlsplit(dsn).path.lstrip("/")
    if not ALLOWED_DB.match(name):
        raise SystemExit(f"refusing to write synthetic data into database '{name}': only mygovt_test*, "
                         "mygovt_dev* and mygovt_synth* databases are allowed")
    return name


async def _sla(conn, category_id):
    row = await conn.fetchrow(
        "SELECT c.default_priority, c.default_sla_hours, c.default_department_id, "
        "       (SELECT resolution_hours FROM complaints.sla_rule s WHERE s.category_id=c.category_id AND s.priority=c.default_priority LIMIT 1) rh, "
        "       (SELECT escalation_hours FROM complaints.sla_rule s WHERE s.category_id=c.category_id AND s.priority=c.default_priority LIMIT 1) eh "
        "FROM complaints.complaint_category c WHERE c.category_id=$1", category_id)
    return row


async def apply(conn: asyncpg.Connection, batch: str, citizens, complaints, replace: bool) -> dict:
    from app.security.jwt import hash_password

    stats = {"citizens_created": 0, "citizens_skipped": 0, "complaints_created": 0,
             "complaints_skipped": 0, "complaints_rejected": 0, "deleted": 0}
    if replace:
        # delete only rows carrying this batch label
        d = await conn.execute("DELETE FROM complaints.complaint WHERE is_synthetic AND synthetic_batch=$1", batch)
        stats["deleted"] += int(d.split()[-1])
        await conn.execute("DELETE FROM identity.consent WHERE citizen_id IN (SELECT citizen_id FROM identity.citizen WHERE is_synthetic AND synthetic_batch=$1)", batch)
        await conn.execute("DELETE FROM identity.citizen_profile WHERE citizen_id IN (SELECT citizen_id FROM identity.citizen WHERE is_synthetic AND synthetic_batch=$1)", batch)
        d = await conn.execute("DELETE FROM identity.citizen WHERE is_synthetic AND synthetic_batch=$1", batch)
        stats["deleted"] += int(d.split()[-1])
        await conn.execute("DELETE FROM identity.app_user WHERE is_synthetic AND email LIKE $1", f"synthetic{batch.removeprefix('synth-seed')}-%@{SYNTH_DOMAIN}")

    unusable = hash_password(secrets.token_urlsafe(32))     # random secret, discarded: nobody can log in
    for c in citizens:
        if await conn.fetchval("SELECT 1 FROM identity.citizen WHERE citizen_id=$1", c.citizen_id):
            stats["citizens_skipped"] += 1
            continue
        await conn.execute(
            "INSERT INTO identity.app_user (user_id,email,password_hash,role,status,is_synthetic) VALUES ($1,$2,$3,'citizen','active',true)",
            c.user_id, c.email, unusable)
        await conn.execute(
            "INSERT INTO identity.citizen (citizen_id,user_id,name,is_synthetic,synthetic_batch) VALUES ($1,$2,$3,true,$4)",
            c.citizen_id, c.user_id, c.name, batch)
        if c.has_profile:
            p = c.profile
            await conn.execute(
                "INSERT INTO identity.citizen_profile (citizen_id,gender,occupation,annual_income,social_category,residence_type,"
                "district_id,family_size,is_student,bpl_status,disability_status) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
                c.citizen_id, p["gender"], p["occupation"], p["annual_income"], p["social_category"], p["residence_type"],
                p["district_id"], p["family_size"], p["is_student"], p["bpl_status"], p["disability_status"])
            await conn.execute("INSERT INTO identity.consent (citizen_id,purpose,granted) VALUES ($1,'profile_based_scheme_matching',true)", c.citizen_id)
        stats["citizens_created"] += 1

    for k in complaints:
        if await conn.fetchval("SELECT 1 FROM complaints.complaint WHERE complaint_ref=$1", k.ref):
            stats["complaints_skipped"] += 1
            continue
        cat = await _sla(conn, k.category_id)
        if cat is None:
            stats["complaints_rejected"] += 1
            continue
        res_h, esc_h = rules.compute_deadlines(k.created_at, cat["rh"] or cat["default_sla_hours"], cat["eh"])
        due, esc_due = res_h, esc_h
        if k.scenario == "resolved_late":
            # resolve AFTER the deadline
            k.step_times[-1] = max(k.step_times[-1], due + timedelta(hours=3))
        if k.scenario == "resolved_on_time":
            k.step_times[-1] = min(k.step_times[-1], due - timedelta(minutes=30))
            k.step_times = sorted(k.step_times)
        dept = cat["default_department_id"]
        auth = await conn.fetchval("SELECT authority_id FROM administration.authority WHERE department_id=$1 AND is_routing_placeholder LIMIT 1", dept) if dept else None
        cit = citizens[k.citizen_index]
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO complaints.complaint (complaint_id,complaint_ref,citizen_id,title,description,category_id,category_confidence,"
                "department_id,authority_id,priority,status,district_id,created_at,due_date,escalation_due_at,is_synthetic,synthetic_batch) "
                "VALUES ($1,$2,$3,$4,$5,$6,1.0,$7,$8,$9,$10,$11,$12,$13,$14,true,$15)",
                k.complaint_id, k.ref, cit.citizen_id, f"[SYNTHETIC] {k.title}", BODY, k.category_id, dept, auth,
                cat["default_priority"], k.path[0], k.district_id, k.created_at, due, esc_due, batch)
            for old, new in zip(k.path, k.path[1:], strict=False):
                assert rules.can_transition(old, new), (old, new)
                await conn.execute("UPDATE complaints.complaint SET status=$2 WHERE complaint_id=$1", k.complaint_id, new)
            if k.path[-1] == "resolved" or k.path[-1] == "closed":
                rt = k.step_times[k.path.index("resolved")]
                await conn.execute("UPDATE complaints.complaint SET resolved_at=$2 WHERE complaint_id=$1", k.complaint_id, rt)
            # rewrite the trigger-generated history timestamps so the timeline is plausible
            hist = await conn.fetch("SELECT history_id FROM complaints.complaint_history WHERE complaint_id=$1 ORDER BY history_id", k.complaint_id)
            for h, ts in zip(hist, k.step_times, strict=True):
                await conn.execute("UPDATE complaints.complaint_history SET changed_at=$2 WHERE history_id=$1", h["history_id"], ts)
            await conn.execute("UPDATE complaints.complaint SET created_at=$2, updated_at=$3 WHERE complaint_id=$1",
                               k.complaint_id, k.created_at, k.step_times[-1])
        stats["complaints_created"] += 1
    return stats


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--citizens", type=int, default=50)
    ap.add_argument("--complaints", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true", help="plan and validate inside a transaction, then roll back")
    ap.add_argument("--replace", action="store_true", help="delete this seed's synthetic rows first")
    args = ap.parse_args(argv)

    db = check_target(args.dsn)
    conn = await asyncpg.connect(args.dsn)
    try:
        if not await conn.fetchval("SELECT 1 FROM information_schema.columns WHERE table_schema='complaints' "
                                   "AND table_name='complaint' AND column_name='is_synthetic'"):
            print("migration 007 (synthetic flags) is not applied", file=sys.stderr)
            return 2
        # only categories that route to a department with a routing authority, so generated complaints are routable
        cats = [r[0] for r in await conn.fetch(
            "SELECT c.category_id FROM complaints.complaint_category c WHERE c.is_active AND EXISTS "
            "(SELECT 1 FROM administration.authority a WHERE a.department_id = c.default_department_id) ORDER BY 1")]
        dists = [r[0] for r in await conn.fetch("SELECT district_id FROM administration.district ORDER BY 1")]
        if not cats or not dists:
            print("seed data missing: run `python -m scripts.seed` first", file=sys.stderr)
            return 2
        batch, citizens, complaints = plan(args.seed, args.citizens, args.complaints, cats, dists)
        tx = conn.transaction()
        await tx.start()
        try:
            stats = await apply(conn, batch, citizens, complaints, args.replace)
        except Exception:
            await tx.rollback()
            raise
        if args.dry_run:
            await tx.rollback()
            print("dry-run: rolled back")
        else:
            await tx.commit()
        print(f"database={db} batch={batch}")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
