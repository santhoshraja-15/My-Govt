"""Health check endpoints for all services."""
import asyncio
from datetime import datetime, timezone

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


async def check_postgres() -> dict:
    from app.core.database import check_db_health
    return await check_db_health()


async def check_neo4j() -> dict:
    if not settings.FEATURE_GRAPH:
        return {"status": "disabled"}
    try:
        from neo4j import AsyncGraphDatabase
        driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS ok")
            await result.single()
        await driver.close()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_redis() -> dict:
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
        await client.ping()
        await client.aclose()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_minio() -> dict:
    def _probe() -> None:
        import urllib3
        from minio import Minio

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
            http_client=urllib3.PoolManager(timeout=urllib3.Timeout(connect=2, read=3), retries=urllib3.Retry(total=0)),
        )
        client.list_buckets()

    try:
        # The MinIO SDK is blocking: run it in a worker thread so a missing optional service cannot stall the event loop
        # (and thereby make the other, healthy checks time out).
        await asyncio.wait_for(asyncio.to_thread(_probe), timeout=6)
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e) or type(e).__name__}


def _redact(result: dict) -> dict:
    """Public health shows state only: exception text can reveal internal hostnames and driver details."""
    return {k: v for k, v in result.items() if k != "error"}


async def get_health_status(detailed: bool = False) -> dict:
    """Aggregate health check for all services."""
    checks = await asyncio.gather(
        asyncio.wait_for(check_postgres(), timeout=8),
        asyncio.wait_for(check_neo4j(), timeout=8),
        asyncio.wait_for(check_redis(), timeout=8),
        asyncio.wait_for(check_minio(), timeout=8),
        return_exceptions=True,
    )

    def _norm(r: object) -> dict:
        if isinstance(r, BaseException):
            return {"status": "unhealthy", "error": str(r) or type(r).__name__}
        return r if isinstance(r, dict) else {"status": "unhealthy", "error": "unexpected result"}

    results = {name: _norm(r) for name, r in zip(("postgresql", "neo4j", "redis", "minio"), checks, strict=True)}
    if not detailed:
        results = {name: _redact(r) for name, r in results.items()}

    all_healthy = all(v.get("status") in ("healthy", "disabled") for v in results.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "services": results,
    }
