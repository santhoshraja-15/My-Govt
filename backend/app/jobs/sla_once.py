"""Run one SLA escalation pass and exit.   python -m app.jobs.sla_once

Same logic as the long-running scheduler (app.jobs.scheduler), for cron / manual use. Exit code 0 on
success (prints how many complaints were escalated), 1 if the pass failed.
"""
from __future__ import annotations

import asyncio
import sys

from app.jobs.scheduler import escalate_overdue_complaints


async def main() -> int:
    try:
        count = await escalate_overdue_complaints()
    except Exception as e:  # noqa: BLE001 - report and signal failure to the caller (cron)
        print(f"SLA pass failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"escalated {count} overdue complaint(s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
