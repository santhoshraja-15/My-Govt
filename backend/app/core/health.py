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
        client = aioredis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_minio() -> dict:
    try:
        from minio import Minio
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )
        client.list_buckets()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def get_health_status() -> dict:
    """Aggregate health check for all services."""
    checks = await asyncio.gather(
        check_postgres(),
        check_neo4j(),
        check_redis(),
        check_minio(),
        return_exceptions=True,
    )

    def _norm(r: object) -> dict:
        if isinstance(r, BaseException):
            return {"status": "unhealthy", "error": str(r)}
        return r if isinstance(r, dict) else {"status": "unhealthy", "error": "unexpected result"}

    results = {name: _norm(r) for name, r in zip(("postgresql", "neo4j", "redis", "minio"), checks, strict=True)}

    all_healthy = all(v.get("status") in ("healthy", "disabled") for v in results.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "services": results,
    }
