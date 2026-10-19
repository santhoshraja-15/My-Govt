"""Persistence audit across a server restart (Workflow E).

    python -m scripts.audit_persistence create --state state.json [--api http://127.0.0.1:8000] [--dsn postgresql://.../mygovt_dev_demo]
    ... restart the API process ...
    python -m scripts.audit_persistence verify --state state.json [--api ...] [--dsn ...]

`create` registers a disposable citizen, files a complaint, has the demo officer assign it and move it to in-progress with a remark,
and checks every step through the API AND directly in PostgreSQL. `verify` repeats the reads after a restart. The created records
are labelled (title prefix "AUDIT-PERSISTENCE") and are left in place: this tool never deletes data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
import urllib.error
import urllib.request

import asyncpg

failures: list[str] = []


def call(api: str, method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(api + "/api/v1" + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(label: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail else ""))
    if not cond:
        failures.append(label)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["create", "verify"])
    ap.add_argument("--state", required=True)
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--dsn", default="postgresql://postgres@localhost:5432/mygovt_dev_demo")
    a = ap.parse_args()
    api = a.api.rstrip("/")
    db = await asyncpg.connect(a.dsn)

    if a.mode == "create":
        email, password = f"persist-{secrets.token_hex(4)}@example.com", "Persist-test-pass-1"
        s, _ = call(api, "POST", "/auth/register", body={"email": email, "password": password, "full_name": "Persistence Audit"})
        check("register citizen", s == 201, str(s))
        s, login = call(api, "POST", "/auth/login", body={"email": email, "password": password})
        token = login["access_token"]
        cats = call(api, "GET", "/complaints/categories/list")[1]
        # the demo officer belongs to the first routable department, so use a category that routes to it
        o_s, olog = call(api, "POST", "/auth/login", body={"email": "officer@demo.example", "password": "Demo@12345"})
        otoken = olog["access_token"]
        dept = call(api, "GET", "/complaints/assigned?limit=1", otoken)[1]["department_scope"]
        cat = await db.fetchval("SELECT category_id FROM complaints.complaint_category WHERE default_department_id=$1 AND is_active ORDER BY 1 LIMIT 1", dept)
        check("a category routes to the officer's department", cat is not None and any(c["category_id"] == cat for c in cats))
        s, c = call(api, "POST", "/complaints", token, {"title": "AUDIT-PERSISTENCE pothole check", "description": "Created by the persistence audit to prove records survive a restart.", "category_id": cat})
        check("file complaint", s == 201, str(s))
        ref, cid = c["reference_number"], c["complaint_id"]
        row = await db.fetchrow("SELECT status, department_id, citizen_id FROM complaints.complaint WHERE complaint_ref=$1", ref)
        check("row exists in PostgreSQL right after submission", row is not None and row["department_id"] == dept, f"{ref} status={row['status'] if row else None}")
        s, out = call(api, "POST", f"/complaints/{cid}/assign", otoken, {})
        check("officer assigns", s == 200 and out["status"] == "assigned", str(out))
        s, _ = call(api, "PATCH", f"/complaints/{cid}/status", otoken, {"new_status": "in_progress", "remarks": "Persistence audit: crew dispatched"})
        check("officer moves it to in progress", s == 200, str(s))
        row = await db.fetchrow("SELECT status, assigned_officer_id FROM complaints.complaint WHERE complaint_ref=$1", ref)
        hist = [h["new_status"] for h in await db.fetch("SELECT new_status FROM complaints.complaint_history h JOIN complaints.complaint c USING (complaint_id) WHERE c.complaint_ref=$1 ORDER BY history_id", ref)]
        check("database shows in_progress with an officer", row["status"] == "in_progress" and row["assigned_officer_id"] is not None)
        check("history trigger recorded every step", hist[-2:] == ["assigned", "in_progress"], str(hist))
        with open(a.state, "w", encoding="utf-8") as fh:
            json.dump({"email": email, "password": password, "ref": ref, "complaint_id": cid, "history": hist}, fh)
        print(f"state saved to {a.state}; restart the API, then run: verify --state {a.state}")
    else:
        with open(a.state, encoding="utf-8") as fh:
            st = json.load(fh)
        s, login = call(api, "POST", "/auth/login", body={"email": st["email"], "password": st["password"]})
        check("citizen can still sign in after the restart", s == 200, str(s))
        token = login["access_token"]
        s, detail = call(api, "GET", f"/complaints/{st['complaint_id']}", token)
        check("complaint is still readable through the API", s == 200 and detail["reference_number"] == st["ref"], str(s))
        check("status survived", detail.get("status") == "in_progress", detail.get("status", ""))
        check("officer remark survived in the timeline", any((t.get("remarks") or "").startswith("Persistence audit") for t in detail.get("timeline", [])))
        check("assignment survived", bool(detail.get("officer_name")), str(detail.get("officer_name")))
        s, mine = call(api, "GET", "/complaints/mine", token)
        check("complaint is listed in my complaints", any(i["reference_number"] == st["ref"] for i in mine.get("items", [])))
        s, track = call(api, "GET", f"/complaints/track/{st['ref']}")
        check("public tracking by reference still works", s == 200 and track["status"] == "in_progress", str(s))
        row = await db.fetchrow("SELECT status FROM complaints.complaint WHERE complaint_ref=$1", st["ref"])
        check("PostgreSQL still holds the row", row is not None and row["status"] == "in_progress")
    await db.close()
    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
