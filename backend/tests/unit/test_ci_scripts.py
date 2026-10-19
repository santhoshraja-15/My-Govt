"""The CI helper that judges /health must accept only the documented degradation (optional MinIO absent)."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "assert_health.py"
_spec = importlib.util.spec_from_file_location("assert_health", _path)
assert _spec and _spec.loader
assert_health = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(assert_health)


def _payload(status, **services):
    return {"status": status, "services": {k: {"status": v} for k, v in services.items()}}


def test_degraded_only_because_optional_minio_is_accepted():
    p = _payload("degraded", postgresql="healthy", neo4j="healthy", redis="healthy", minio="unhealthy")
    assert assert_health.judge(p) == []


def test_all_healthy_is_accepted():
    p = _payload("healthy", postgresql="healthy", neo4j="healthy", redis="healthy", minio="healthy")
    assert assert_health.judge(p) == []


def test_disabled_neo4j_by_feature_flag_is_accepted():
    p = _payload("healthy", postgresql="healthy", neo4j="disabled", redis="healthy", minio="healthy")
    assert assert_health.judge(p) == []


def test_required_service_failure_is_rejected_even_when_minio_is_the_only_documented_gap():
    for broken in ("postgresql", "neo4j", "redis"):
        states = {"postgresql": "healthy", "neo4j": "healthy", "redis": "healthy", "minio": "unhealthy", broken: "unhealthy"}
        assert any(broken in m for m in assert_health.judge(_payload("degraded", **states)))


def test_missing_required_service_is_rejected():
    assert assert_health.judge(_payload("degraded", postgresql="healthy", redis="healthy", minio="unhealthy"))


def test_dishonest_overall_status_is_rejected():
    lying = _payload("healthy", postgresql="healthy", neo4j="healthy", redis="healthy", minio="unhealthy")
    assert assert_health.judge(lying)
    pointless = _payload("degraded", postgresql="healthy", neo4j="healthy", redis="healthy", minio="healthy")
    assert assert_health.judge(pointless)
