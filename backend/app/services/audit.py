"""Application audit trail -> audit.audit_log (append-only at the database level).

Rules: record WHO did WHAT to WHICH record, never secrets or personal data. Passwords, tokens and
profile values are never passed here; callers record field *names*, ids and outcomes only.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
from typing import Any, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def pseudonymise(value: str) -> str:
    """Stable, non-reversible reference for identifiers that must not be stored verbatim (e-mail)."""
    return "h:" + hashlib.sha256(value.strip().lower().encode()).hexdigest()[:16]


def client_ip(request: Any) -> Optional[str]:
    host = getattr(getattr(request, "client", None), "host", None)
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


async def record(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    user: Any = None,
    request: Any = None,
    old: Optional[dict] = None,
    new: Optional[dict] = None,
    outcome: str = "success",
    commit: bool = True,
) -> None:
    """Insert one audit row. Failure to audit is logged but never breaks the user's request."""
    payload = {**(new or {}), "outcome": outcome}
    try:
        async with db.begin_nested():
            await db.execute(
                text("""
                    INSERT INTO audit.audit_log
                        (user_id, user_role, action, entity_type, entity_id, old_value, new_value, ip_address, request_id)
                    VALUES (:uid, :role, :action, :etype, :eid, CAST(:old AS jsonb), CAST(:new AS jsonb),
                            CAST(:ip AS inet), :rid)
                """),
                {
                    "uid": getattr(user, "user_id", None), "role": getattr(user, "role", None) or "anonymous",
                    "action": action, "etype": entity_type, "eid": entity_id,
                    "old": json.dumps(old) if old else None, "new": json.dumps(payload),
                    "ip": client_ip(request),
                    "rid": getattr(getattr(request, "state", None), "request_id", None),
                },
            )
        if commit:
            await db.commit()
    except Exception as e:  # noqa: BLE001 - auditing must not take the request down
        logger.error("audit_write_failed", action=action, error=str(e))
