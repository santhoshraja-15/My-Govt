"""Smoke-check a running DEMO stack through the real HTTP API (stdlib only).

    python check_demo.py [base_url]        default http://localhost:8000

Logs in as each demo role and asserts what the demonstration relies on: role-scoped complaint lists, the citizen's own
complaints, the admin overview, demo eligibility rules and honest verification statuses. Exit 1 on any failure.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
PASSWORD = "Demo@12345"          # fixture credential of the demo database (see docs/demo.md)
failures: list[str] = []


def call(method, path, body=None, token=None):
    req = urllib.request.Request(f"{BASE}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def login(role):
    status, body = call("POST", "/auth/login", {"email": f"{role}@demo.example", "password": PASSWORD})
    check(status == 200, f"{role} can sign in")
    return body.get("access_token"), body.get("user", {})


ctok, cuser = login("citizen")
otok, ouser = login("officer")
o2tok, _ = login("officer2")
atok, auser = login("admin")
check(cuser.get("role") == "citizen" and ouser.get("role") == "officer" and auser.get("role") == "state_admin", "roles are as documented")

s, mine = call("GET", "/complaints/mine", token=ctok)
check(s == 200 and mine["total"] == 6, f"citizen sees their 6 demo complaints (got {mine.get('total')})")
check(len({i["status"] for i in mine["items"]}) >= 4, "the citizen's complaints cover several lifecycle states")

s, staff = call("GET", "/complaints/assigned?limit=200", token=otok)
check(s == 200 and staff["department_name"] and staff["demo_data_included"] is True, f"officer sees their department ({staff.get('department_name')}) in demo mode")
check(all(i["is_synthetic"] for i in staff["items"]) and staff["total"] > 0, "every listed complaint is labelled synthetic")
s, staff2 = call("GET", "/complaints/assigned?limit=200", token=o2tok)
refs1, refs2 = {i["reference_number"] for i in staff["items"]}, {i["reference_number"] for i in staff2["items"]}
check(not (refs1 & refs2), "two departments' officers see disjoint complaints")
s, _ = call("GET", "/complaints/assigned", token=ctok)
check(s == 403, "a citizen is refused the staff list")
other_id = next(i["complaint_id"] for i in staff2["items"])
s, _ = call("GET", f"/complaints/{other_id}", token=otok)
check(s == 403, "an officer cannot open another department's complaint")
s, _ = call("GET", f"/complaints/{other_id}", token=ctok)
check(s == 403, "a citizen cannot open someone else's complaint")

movable = next((i for i in staff["items"] if i["status"] == "classified"), None)
if movable:
    s, out = call("POST", f"/complaints/{movable['complaint_id']}/assign", {}, token=otok)
    check(s == 200 and out["status"] == "assigned", "officer assigns a classified complaint to themselves")
    s, out = call("PATCH", f"/complaints/{movable['complaint_id']}/status", {"new_status": "in_progress", "remarks": "Demo check"}, token=otok)
    check(s == 200, "officer moves it to in progress")
    s, out = call("PATCH", f"/complaints/{movable['complaint_id']}/status", {"new_status": "closed"}, token=otok)
    check(s == 409, "an illegal transition is refused (409)")

s, ov = call("GET", "/admin/overview", token=atok)
check(s == 200 and ov["database_stats"]["demo_data_included"] is True and ov["database_stats"]["complaints_total"] >= 80, "admin overview counts the demo complaints")
check(ov["verification"]["schemes"].get("official_verified", 0) == 0, "no scheme is shown as officially verified")

s, el = call("POST", "/schemes/b0000001-0000-0000-0000-000000000002/eligibility", {"gender": "female", "annual_income": 180000}, token=ctok)
check(s == 200 and el["overall"] == "ELIGIBLE" and el["verification_status"] == "provisional", "demo eligibility rules evaluate (and the scheme stays provisional)")
s, el = call("POST", "/schemes/b0000001-0000-0000-0000-000000000002/eligibility", {"gender": "male", "annual_income": 180000}, token=ctok)
check(s == 200 and el["overall"] == "NOT_ELIGIBLE", "a non-matching profile is NOT_ELIGIBLE")
s, el = call("POST", "/schemes/b0000001-0000-0000-0000-000000000002/eligibility", {"gender": "female"}, token=ctok)
check(s == 200 and el["overall"] not in ("ELIGIBLE",), f"missing data is never guessed as eligible (got {el.get('overall')})")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
