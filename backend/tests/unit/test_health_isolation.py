"""A slow or missing optional service must not make the other health checks fail (hosted CI: Redis reported a
connection timeout because the blocking MinIO SDK stalled the event loop)."""
import asyncio
import sys
import time
import types

import pytest

from app.core import health


@pytest.mark.asyncio
async def test_blocking_minio_probe_does_not_stall_the_event_loop(monkeypatch):
    class SlowMinio:                       # stands in for the synchronous SDK retrying against an unresolvable host
        def __init__(self, *a, **k):
            pass

        def list_buckets(self):
            time.sleep(0.8)
            raise OSError("name resolution failed")

    monkeypatch.setitem(sys.modules, "minio", types.SimpleNamespace(Minio=SlowMinio))

    gaps: list[float] = []

    async def ticker():
        last = time.perf_counter()
        for _ in range(12):
            await asyncio.sleep(0.05)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    t = asyncio.create_task(ticker())
    await asyncio.sleep(0.06)              # let the ticker start (and record a first tick) before the probe runs
    result = await health.check_minio()
    await t
    assert result["status"] == "unhealthy" and "name resolution failed" in result["error"]
    assert max(gaps) < 0.3, f"event loop was blocked for {max(gaps):.2f}s"


@pytest.mark.asyncio
async def test_unhealthy_optional_service_leaves_required_ones_healthy(monkeypatch):
    async def ok():
        return {"status": "healthy"}

    async def down():
        return {"status": "unhealthy", "error": "boom"}

    monkeypatch.setattr(health, "check_postgres", ok)
    monkeypatch.setattr(health, "check_neo4j", ok)
    monkeypatch.setattr(health, "check_redis", ok)
    monkeypatch.setattr(health, "check_minio", down)
    out = await health.get_health_status()
    assert out["status"] == "degraded"
    assert {k: v["status"] for k, v in out["services"].items()} == {
        "postgresql": "healthy", "neo4j": "healthy", "redis": "healthy", "minio": "unhealthy"}
    assert "error" not in out["services"]["minio"]            # public payload stays redacted


@pytest.mark.asyncio
async def test_a_hanging_check_is_bounded_and_reported(monkeypatch):
    async def hang():
        await asyncio.sleep(60)

    async def ok():
        return {"status": "healthy"}

    monkeypatch.setattr(health, "check_postgres", ok)
    monkeypatch.setattr(health, "check_neo4j", ok)
    monkeypatch.setattr(health, "check_redis", hang)
    monkeypatch.setattr(health, "check_minio", ok)

    real_wait_for = asyncio.wait_for

    async def fast_wait_for(coro, timeout):
        return await real_wait_for(coro, timeout=min(timeout, 0.2))

    monkeypatch.setattr(health.asyncio, "wait_for", fast_wait_for)
    out = await health.get_health_status(detailed=True)
    assert out["services"]["redis"]["status"] == "unhealthy" and out["services"]["redis"]["error"]
    assert out["services"]["postgresql"]["status"] == "healthy"
