"""SLA escalation scheduler — runs as a background worker."""
import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logging import setup_logging
from app.services import complaint_rules as rules

setup_logging()
logger = structlog.get_logger(__name__)


async def escalate_overdue_complaints(session_factory=None) -> int:
    """Escalate complaints whose escalation deadline has passed.

    Only statuses from which 'escalated' is a legal transition are touched (see
    complaint_rules.TRANSITIONS). The status-history row is written by the
    trg_complaint_history trigger; we annotate it. When the complaint's authority has a
    parent authority an open complaints.escalation row records the hand-off.
    """
    factory = session_factory or AsyncSessionLocal
    async with factory() as db:
        overdue = (await db.execute(
            text("""
                SELECT complaint_id, authority_id FROM complaints.complaint
                WHERE status = ANY(:statuses)
                  AND escalation_due_at IS NOT NULL AND escalation_due_at < now()
                FOR UPDATE SKIP LOCKED
            """),
            {"statuses": list(rules.ESCALATABLE)},
        )).fetchall()
        for row in overdue:
            await db.execute(
                text("UPDATE complaints.complaint SET status = 'escalated' WHERE complaint_id = :cid"),
                {"cid": row.complaint_id},
            )
            await db.execute(
                text("""
                    UPDATE complaints.complaint_history SET remarks = 'Auto-escalated by SLA scheduler'
                    WHERE history_id = (SELECT max(history_id) FROM complaints.complaint_history
                                        WHERE complaint_id = :cid)
                """),
                {"cid": row.complaint_id},
            )
            await db.execute(
                text("""
                    INSERT INTO complaints.escalation (complaint_id, from_authority_id, to_authority_id, reason)
                    SELECT :cid, a.authority_id, a.parent_authority_id, 'SLA escalation deadline passed'
                    FROM administration.authority a
                    WHERE a.authority_id = :aid AND a.parent_authority_id IS NOT NULL
                """),
                {"cid": row.complaint_id, "aid": row.authority_id},
            )
        await db.commit()
        if overdue:
            logger.info("Escalated overdue complaints", count=len(overdue))
        return len(overdue)


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
