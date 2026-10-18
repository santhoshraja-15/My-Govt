"""SLA escalation scheduler — runs as a background worker."""
import asyncio
import logging
from datetime import datetime, timezone

import structlog
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import setup_logging

setup_logging()
logger = structlog.get_logger(__name__)


async def escalate_overdue_complaints() -> int:
    """Mark complaints that have breached SLA as escalated."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                WITH overdue AS (
                    SELECT complaint_id, status
                    FROM complaints.complaint
                    WHERE status NOT IN ('resolved', 'closed', 'rejected', 'escalated')
                      AND escalation_due_at IS NOT NULL
                      AND escalation_due_at < now()
                )
                UPDATE complaints.complaint c
                SET status = 'escalated', updated_at = now()
                FROM overdue o
                WHERE c.complaint_id = o.complaint_id
                RETURNING c.complaint_id, o.status AS old_status
            """)
        )
        rows = result.fetchall()
        escalated = len(rows)

        if escalated > 0:
            for complaint_id, old_status in rows:
                await db.execute(
                    text("""
                        INSERT INTO complaints.complaint_history
                            (complaint_id, old_status, new_status, remarks, changed_at)
                        VALUES (:cid, :old, 'escalated', 'Auto-escalated by SLA scheduler', now())
                    """),
                    {"cid": str(complaint_id), "old": old_status},
                )
            await db.commit()
            logger.info("Escalated overdue complaints", count=escalated)

    return escalated


async def run_scheduler():
    """Periodic SLA scheduler loop."""
    logger.info("SLA scheduler started", interval_seconds=300)
    while True:
        try:
            count = await escalate_overdue_complaints()
            logger.info("Scheduler tick completed", escalated=count,
                        timestamp=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            logger.error("Scheduler tick failed", error=str(e))
        await asyncio.sleep(300)  # every 5 minutes


if __name__ == "__main__":
    asyncio.run(run_scheduler())
