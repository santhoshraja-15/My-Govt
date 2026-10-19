"""API audit: call EVERY operation of the running API as each demo role and check the access rules.

    python -m scripts.audit_api_matrix [out.csv] [base_url]

Needs the running demo stack (docs/demo.md). Operations that need ids use real ids discovered through the API; operations
that would create or change data are sent an EMPTY body (or a random id), so the expected outcome is a refusal or a
validation error and nothing is written. Login/registration/logout are exercised by the test suites instead.
Exit code 1 when an anomaly (5xx, wrong access decision) is found.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import urllib.error
import urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "api_verification.csv"
BASE = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000").rstrip("/")
PASSWORD = "Demo@12345"
ROLES = ["anonymous", "citizen", "officer", "officer2", "deptadmin", "admin", "sysadmin"]
STAFF = {"officer", "officer2", "deptadmin", "admin", "sysadmin"}
ADMIN = {"admin", "sysadmin"}
SKIP = {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/logout", "/api/v1/auth/refresh"}
UUID0 = "00000000-0000-0000-0000-000000000000"


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, method=method, data=data,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()


def login(local):
    s, raw = call("POST", "/api/v1/auth/login", body={"email": f"{local}@demo.example", "password": PASSWORD})
    assert s == 200, (local, s)
    return json.loads(raw)["access_token"]


def expectation(method, path):
    """Required access rule for a path: (min role class, description)."""
    p = path.removeprefix("/api/v1")
    if p.startswith(("/admin", "/architecture")):
        return "admin"
    if p in ("/complaints/assigned", "/complaints/officers") or re.fullmatch(r"/complaints/\{[^/]+\}/(assign)", p):
        return "staff"
    if re.fullmatch(r"/complaints/\{[^/]+\}/status", p):
        return "staff"
    if p.startswith(("/citizens", "/chat")) or p in ("/auth/me", "/complaints/mine") or (method == "POST" and p == "/complaints") or re.fullmatch(r"/complaints/\{[^/]+\}(/evidence)?", p):
        return "auth"
    return "public"


def judge(need: str, role: str, method: str, s: int) -> str | None:
    """The access decision a response must show for this endpoint class, or None when it is acceptable."""
    if s >= 500 or s == 0:
        return f"{role}:server-error({s})"
    if role == "anonymous":
        return f"anonymous:expected-401({s})" if need in ("auth", "staff", "admin") and s != 401 else None
    if need == "admin" and role not in ADMIN:
        return None if s == 403 else (f"{role}:allowed-but-admin-only({s})" if s < 400 else f"{role}:expected-403({s})")
    if need == "staff" and role not in STAFF:
        return None if s == 403 else f"{role}:expected-403({s})"
    if need == "public" and s in (401, 403) and method == "GET":
        return f"{role}:public-endpoint-refused({s})"
    return None


def main() -> int:
    tokens: dict[str, str | None] = {"anonymous": None}
    for role in ROLES[1:]:
        tokens[role] = login(role)
    spec = json.loads(call("GET", "/api/openapi.json")[1])
    ids = {
        "scheme": json.loads(call("GET", "/api/v1/schemes?page_size=1")[1])["items"][0]["scheme_id"],
        "service": json.loads(call("GET", "/api/v1/services?page_size=1")[1])["items"][0]["service_id"],
        "department": json.loads(call("GET", "/api/v1/departments")[1])[0]["department_id"],
    }
    rows, anomalies = [], 0
    for path, item in sorted(spec["paths"].items()):
        for method, op in item.items():
            if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE") or path in SKIP:
                continue
            url = path
            for param in re.findall(r"\{([^}]+)\}", path):
                url = url.replace("{" + param + "}", {
                    "scheme_id": ids["scheme"], "service_id": ids["service"], "department_id": str(ids["department"]),
                    "schema_name": "schemes", "table_name": "scheme", "reference": "MYG-0000-000000", "table": "scheme", "schema": "schemes",
                    "example_id": "schemes_by_department"}.get(param, UUID0))
            if "{schema}" in path and "{table}" in path:
                url = url.replace(UUID0, "scheme")
            body: dict | None = {} if method.upper() in ("POST", "PUT", "PATCH") else None
            need = expectation(method.upper(), path)
            statuses: dict[str, int] = {}
            for role in ROLES:
                s, raw = call(method.upper(), url, tokens[role], body)
                statuses[role] = s
            verdicts = [v for role, s in statuses.items() if (v := judge(need, role, method.upper(), s))]
            row = {"method": method.upper(), "path": path, "operation": op.get("summary") or op.get("operationId", ""), "access_rule": need,
                   **{f"status_{r}": statuses[r] for r in ROLES}, "result": "PASS" if not verdicts else "ANOMALY", "anomalies": "; ".join(verdicts)}
            anomalies += bool(verdicts)
            rows.append(row)
            print(f"{row['result']:8} {method.upper():6} {path:58} " + " ".join(f"{statuses[r]:>3}" for r in ROLES) + (f"   {row['anomalies']}" if verdicts else ""))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} operations, {anomalies} anomalies -> {OUT}  (roles in column order: {', '.join(ROLES)})")
    return 1 if anomalies else 0


if __name__ == "__main__":
    sys.exit(main())
