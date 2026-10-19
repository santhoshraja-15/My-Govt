"""Judge a /health payload for the Compose CI job without hiding real failures.

Required services must be "healthy" (or "disabled" by feature flag). Optional services (object storage is opt-in and
not implemented yet) may be anything. The overall status may be "degraded" only when every non-healthy service is optional.
Usage: python assert_health.py <health.json>   -> exit 1 on a violation; prints a ::notice with the observed states.
"""
import json
import sys

REQUIRED = ("postgresql", "neo4j", "redis")
OPTIONAL = ("minio",)
OK = ("healthy", "disabled")


def judge(payload: dict) -> list[str]:
    problems = []
    services = payload.get("services") or {}
    for name in REQUIRED:
        state = (services.get(name) or {}).get("status")
        if state not in OK:
            problems.append(f"required service '{name}' is {state!r}")
    unhealthy = {n for n, v in services.items() if (v or {}).get("status") not in OK}
    unexpected = unhealthy - set(OPTIONAL) - set(REQUIRED)
    if unexpected:
        problems.append(f"unknown services not healthy: {sorted(unexpected)}")
    overall = payload.get("status")
    if overall == "healthy" and unhealthy:
        problems.append("overall status says healthy while a service is not")
    if overall not in ("healthy", "degraded"):
        problems.append(f"unexpected overall status {overall!r}")
    if overall == "degraded" and not unhealthy:
        problems.append("overall status is degraded but every service is healthy")
    return problems


if __name__ == "__main__":
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    states = {n: (v or {}).get("status") for n, v in (data.get("services") or {}).items()}
    print(f"::notice title=health payload::overall={data.get('status')} env={data.get('environment')} services={states}")
    issues = judge(data)
    for i in issues:
        print(f"::error title=health check::{i}")
    sys.exit(1 if issues else 0)
