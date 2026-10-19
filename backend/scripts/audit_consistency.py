"""Data-consistency audit: every number the UI/API reports is recomputed from the database and compared.

    python -m scripts.audit_consistency --dsn postgresql://postgres@localhost:5432/mygovt_dev_demo [--api http://127.0.0.1:8000] [--csv out.csv]

Needs the running demo stack (docs/demo.md) and read access to its database. Writes nothing. Exit code 1 on any mismatch.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import urllib.request
from typing import Any

import asyncpg

ROWS: list[dict[str, Any]] = []


def call(api: str, path: str, token: str | None = None, body: Any = None) -> Any:
    req = urllib.request.Request(api + path, method="POST" if body is not None else "GET", data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def check(area: str, what: str, expected: Any, actual: Any) -> None:
    ok = expected == actual
    ROWS.append({"area": area, "check": what, "expected_from_database": expected, "reported_by_application": actual, "result": "PASS" if ok else "FAIL"})
    print(("PASS " if ok else "FAIL ") + f"{area:12} {what}: db={expected} app={actual}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--csv")
    a = ap.parse_args()
    api = a.api.rstrip("/") + "/api/v1"
    db = await asyncpg.connect(a.dsn)

    def login(local: str) -> str:
        return call(api, "/auth/login", body={"email": f"{local}@demo.example", "password": "Demo@12345"})["access_token"]

    admin, citizen, officer = login("admin"), login("citizen"), login("officer")
    demo = (await db.fetchval("SELECT current_database()")).startswith("mygovt_dev")

    # public statistics ---------------------------------------------------------------------------------
    s = call(api, "/public/stats")
    check("public stats", "active schemes", await db.fetchval("SELECT count(*) FROM schemes.scheme WHERE status='active'"), s["schemes"])
    check("public stats", "active services", await db.fetchval("SELECT count(*) FROM services.service WHERE status='active'"), s["services"])
    check("public stats", "active departments", await db.fetchval("SELECT count(*) FROM administration.department WHERE status='active'"), s["departments"])
    check("public stats", "districts", await db.fetchval("SELECT count(*) FROM administration.district"), s["districts"])
    check("public stats", "verified schemes", await db.fetchval("SELECT count(*) FROM schemes.scheme WHERE verification_status='official_verified'"), s["verified_schemes"])

    # catalogue lists -------------------------------------------------------------------------------------
    check("catalogue", "scheme list total", await db.fetchval("SELECT count(*) FROM schemes.scheme WHERE status='active'"), call(api, "/schemes?page_size=100")["total"])
    check("catalogue", "service list total", await db.fetchval("SELECT count(*) FROM services.service WHERE status='active'"), call(api, "/services?page_size=100")["total"])
    for cat in call(api, "/schemes/categories/list"):
        check("catalogue", f"scheme category '{cat}'", await db.fetchval("SELECT count(*) FROM schemes.scheme WHERE category=$1 AND status='active'", cat),
              call(api, f"/schemes?category={cat}&page_size=100")["total"])
    for cat in call(api, "/services/categories/list"):
        check("catalogue", f"service category '{cat}'", await db.fetchval("SELECT count(*) FROM services.service WHERE category=$1 AND status='active'", cat),
              call(api, f"/services?category={cat}&page_size=100")["total"])
    sid = await db.fetchval("SELECT scheme_id FROM schemes.scheme ORDER BY scheme_name LIMIT 1")
    detail = call(api, f"/schemes/{sid}")
    check("catalogue", "scheme detail eligibility rule count", await db.fetchval("SELECT count(*) FROM schemes.eligibility_rule WHERE scheme_id=$1", sid), len(detail["eligibility_rules"]))
    check("catalogue", "scheme detail verification status", await db.fetchval("SELECT verification_status FROM schemes.scheme WHERE scheme_id=$1", sid), detail["verification_status"])

    # admin dashboard -------------------------------------------------------------------------------------
    ov = call(api, "/admin/overview", admin)["database_stats"]
    syn = "" if demo else "NOT is_synthetic AND "
    open_ = "status NOT IN ('resolved','closed','rejected')"
    where = "TRUE" if demo else "NOT is_synthetic"
    check("admin", "complaints total", await db.fetchval(f"SELECT count(*) FROM complaints.complaint WHERE {where}"), ov["complaints_total"])
    check("admin", "complaints open", await db.fetchval(f"SELECT count(*) FROM complaints.complaint WHERE {syn}{open_}"), ov["complaints_open"])
    check("admin", "SLA target missed", await db.fetchval(f"SELECT count(*) FROM complaints.complaint WHERE {syn}due_date < now() AND {open_}"), ov["complaints_sla_breached"])
    check("admin", "without an authority", await db.fetchval(f"SELECT count(*) FROM complaints.complaint WHERE {syn}authority_id IS NULL AND {open_}"), ov["complaints_unassigned"])
    check("admin", "synthetic complaints (always counted)", await db.fetchval("SELECT count(*) FROM complaints.complaint WHERE is_synthetic"), ov["synthetic_complaints"])
    check("admin", "documents", await db.fetchval("SELECT count(*) FROM documents.document"), ov["documents"])
    ver = call(api, "/admin/overview", admin)["verification"]
    for key, table in (("schemes", "schemes.scheme"), ("services", "services.service"), ("departments", "administration.department"), ("districts", "administration.district")):
        rows = await db.fetch(f"SELECT verification_status, count(*) c FROM {table} GROUP BY 1")
        check("admin", f"verification breakdown: {key}", {r[0]: r[1] for r in rows}, ver[key])
    perf = {p["department_name"]: p for p in call(api, "/admin/department-performance", admin)}
    for r in await db.fetch(f"""SELECT d.department_name, count(*) total,
            count(*) FILTER (WHERE c.status IN ('resolved','closed')) resolved,
            count(*) FILTER (WHERE c.due_date < now() AND c.{open_.replace('status', 'status')}) breached
            FROM administration.department d JOIN complaints.complaint c ON c.department_id = d.department_id AND {where.replace('is_synthetic', 'c.is_synthetic')}
            GROUP BY d.department_name"""):
        p = perf.get(r["department_name"], {})
        check("admin", f"department performance: {r['department_name']}", (r["total"], r["resolved"], r["breached"]), (p.get("total"), p.get("resolved"), p.get("sla_breached")))

    # staff console -----------------------------------------------------------------------------------------
    staff = call(api, "/complaints/assigned?limit=200", officer)
    dept = staff["department_scope"]
    counts = {r[0]: r[1] for r in await db.fetch(f"SELECT status, count(*) FROM complaints.complaint WHERE department_id=$1 AND {where} GROUP BY 1", dept)}
    check("officer", "status counts of the officer's department", counts, staff["status_counts"])
    check("officer", "overdue", await db.fetchval(f"SELECT count(*) FROM complaints.complaint WHERE department_id=$1 AND {where} AND due_date < now() AND {open_}", dept), staff["overdue"])
    check("officer", "unassigned", await db.fetchval(f"SELECT count(*) FROM complaints.complaint WHERE department_id=$1 AND {where} AND assigned_officer_id IS NULL AND {open_}", dept), staff["unassigned"])
    check("officer", "department name", await db.fetchval("SELECT department_name FROM administration.department WHERE department_id=$1", dept), staff["department_name"])
    check("officer", "listed complaints all in own department", 0, await db.fetchval("SELECT count(*) FROM complaints.complaint WHERE complaint_ref = ANY($1) AND department_id <> $2", [i["reference_number"] for i in staff["items"]], dept))

    # citizen dashboard source ------------------------------------------------------------------------------
    mine = call(api, "/complaints/mine?page_size=100", citizen)
    cid = await db.fetchval("SELECT c.citizen_id FROM identity.citizen c JOIN identity.app_user u ON u.user_id=c.user_id WHERE u.email='citizen@demo.example'")
    check("citizen", "own complaint count", await db.fetchval("SELECT count(*) FROM complaints.complaint WHERE citizen_id=$1", cid), mine["total"])
    check("citizen", "own complaint statuses", sorted(r[0] for r in await db.fetch("SELECT status FROM complaints.complaint WHERE citizen_id=$1", cid)), sorted(i["status"] for i in mine["items"]))
    check("citizen", "history rows equal timeline length", await db.fetchval("SELECT count(*) FROM complaints.complaint_history WHERE complaint_id=(SELECT complaint_id FROM complaints.complaint WHERE complaint_ref=$1)", mine["items"][0]["reference_number"]),
          len(call(api, f"/complaints/{mine['items'][0]['complaint_id']}", citizen)["timeline"]))

    # structural integrity ------------------------------------------------------------------------------------
    check("integrity", "duplicate complaint references", 0, await db.fetchval("SELECT count(*) - count(DISTINCT complaint_ref) FROM complaints.complaint"))
    check("integrity", "complaints without a history row", 0, await db.fetchval("SELECT count(*) FROM complaints.complaint c WHERE NOT EXISTS (SELECT 1 FROM complaints.complaint_history h WHERE h.complaint_id=c.complaint_id)"))
    check("integrity", "history ends in the complaint's current status", 0, await db.fetchval(
        "SELECT count(*) FROM complaints.complaint c WHERE c.status <> (SELECT new_status FROM complaints.complaint_history h WHERE h.complaint_id=c.complaint_id ORDER BY history_id DESC LIMIT 1)"))
    check("integrity", "official_verified records without a source document", 0, await db.fetchval(
        "SELECT (SELECT count(*) FROM schemes.scheme WHERE verification_status='official_verified' AND source_document_ref IS NULL) + (SELECT count(*) FROM administration.department WHERE verification_status='official_verified' AND source_document_ref IS NULL)"))
    check("integrity", "complaints assigned to an officer of another department", 0, await db.fetchval(
        "SELECT count(*) FROM complaints.complaint c JOIN administration.officer o ON o.officer_id=c.assigned_officer_id WHERE o.department_id <> c.department_id"))
    check("integrity", "synthetic rows are labelled in their title", 0, await db.fetchval("SELECT count(*) FROM complaints.complaint WHERE is_synthetic AND title NOT LIKE '[SYNTHETIC]%'"))
    await db.close()

    fails = [r for r in ROWS if r["result"] == "FAIL"]
    print(f"\n{len(ROWS)} checks, {len(fails)} mismatches")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(ROWS[0].keys()))
            w.writeheader()
            w.writerows(ROWS)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
