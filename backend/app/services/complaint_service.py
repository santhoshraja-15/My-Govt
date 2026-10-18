"""Complaint service — submission, classification, routing, SLA.

Column names follow database/schema/001_schema.sql (+ migrations 002/003). Status history is
written by the ``trg_complaint_history`` trigger; this service only annotates the row the
trigger creates (remarks / changed_by) so history is never duplicated.
"""
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.complaints import (
    ComplaintCreate, ComplaintDetail, ComplaintHistoryItem, ComplaintListResponse,
    ComplaintOut, ComplaintStatusUpdate, ComplaintTrack,
)
from app.services import complaint_rules as rules

logger = structlog.get_logger(__name__)

# Backwards-compatible alias (older imports referenced the private name)
_TRANSITIONS = rules.TRANSITIONS


class ComplaintNotFound(LookupError):
    pass


class ComplaintForbidden(PermissionError):
    pass


class InvalidTransition(ValueError):
    pass


_HISTORY_COLS = ["changed_at", "old_status", "new_status", "remarks", "changed_by_role"]


class ComplaintService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── submit ────────────────────────────────────────────────────────────────
    async def submit(self, data: ComplaintCreate, user_id) -> ComplaintOut:
        u = await self.db.execute(
            text("SELECT citizen_id FROM identity.citizen WHERE user_id = :uid"), {"uid": user_id}
        )
        citizen_id = u.scalar()
        if citizen_id is None:
            raise ValueError("Only registered citizens can file complaints")

        category = None
        if data.category_id is not None:
            cr = await self.db.execute(
                text("""
                    SELECT category_name, default_priority, default_department_id, default_sla_hours
                    FROM complaints.complaint_category
                    WHERE category_id = :cid AND is_active = true
                """),
                {"cid": data.category_id},
            )
            category = cr.fetchone()
            if category is None:
                raise ValueError(f"Unknown complaint category {data.category_id}")
        priority = category.default_priority if category else "medium"

        # Jurisdiction (needs PostGIS). The DB trigger also fills these; resolving here lets us
        # route on district. Never overwrite a caller-supplied district with NULL.
        ward_id = local_body_id = taluk_id = None
        district_id = data.district_id
        if data.latitude is not None and data.longitude is not None:
            try:
                async with self.db.begin_nested():  # savepoint: a failure must not abort the tx
                    jr = await self.db.execute(
                        text("SELECT ward_id, local_body_id, taluk_id, district_id "
                             "FROM administration.resolve_jurisdiction(:lon, :lat)"),
                        {"lon": data.longitude, "lat": data.latitude},
                    )
                    jrow = jr.fetchone()
                    if jrow:
                        ward_id, local_body_id, taluk_id = jrow.ward_id, jrow.local_body_id, jrow.taluk_id
                        district_id = jrow.district_id or district_id
            except Exception as e:  # noqa: BLE001
                logger.warning("jurisdiction_resolution_failed", error=str(e))

        department_id, authority_id, placeholder = await self._route_complaint(
            data.category_id, district_id, category.default_department_id if category else None
        )
        resolution_h, escalation_h = await self._sla_hours(
            data.category_id, priority, department_id, category.default_sla_hours if category else None
        )
        now = datetime.now(timezone.utc)
        due_date, escalation_due_at = rules.compute_deadlines(now, resolution_h, escalation_h)
        status = rules.initial_status(category is not None)

        ins = await self.db.execute(
            text("""
                INSERT INTO complaints.complaint (
                    citizen_id, title, description, category_id, category_confidence,
                    department_id, authority_id, priority, status, is_anonymous,
                    latitude, longitude, address,
                    ward_id, local_body_id, taluk_id, district_id,
                    due_date, escalation_due_at
                ) VALUES (
                    :citizen_id, :title, :description, :category_id, :confidence,
                    :department_id, :authority_id, :priority, :status, :anon,
                    :lat, :lon, :address,
                    :ward_id, :lb_id, :taluk_id, :district_id,
                    :due_date, :esc_due
                ) RETURNING complaint_id, complaint_ref, created_at
            """),
            {
                "citizen_id": citizen_id, "title": data.title, "description": data.description,
                "category_id": data.category_id, "confidence": 1.0 if category else None,
                "department_id": department_id, "authority_id": authority_id,
                "priority": priority, "status": status, "anon": data.is_anonymous,
                "lat": data.latitude, "lon": data.longitude, "address": data.address,
                "ward_id": ward_id, "lb_id": local_body_id, "taluk_id": taluk_id,
                "district_id": district_id, "due_date": due_date, "esc_due": escalation_due_at,
            },
        )
        new = ins.fetchone()
        assert new is not None  # INSERT ... RETURNING always yields a row
        await self.db.commit()

        dept_name = None
        if department_id:
            dn = await self.db.execute(
                text("SELECT department_name FROM administration.department WHERE department_id = :d"),
                {"d": department_id},
            )
            dept_name = dn.scalar()
        return ComplaintOut(
            complaint_id=new.complaint_id,
            reference_number=new.complaint_ref,
            title=data.title,
            status=status,
            category_name=category.category_name if category else None,
            department_name=dept_name,
            created_at=new.created_at,
            due_date=due_date,
            assignment_state=rules.assignment_state(authority_id, placeholder, department_id),
        )

    async def _route_complaint(self, category_id, district_id, default_department_id):
        """Deterministic routing: routing_rule -> department; then nearest authority.

        Authority choice: the district authority of the complaint's own district, else the
        state-level authority of that department. Returns (department_id, authority_id);
        either may be None when no rule/authority is configured (no guessing).
        """
        if category_id is None:
            return None, None, False
        r = await self.db.execute(
            text("""
                SELECT department_id FROM complaints.routing_rule
                WHERE category_id = :cat ORDER BY priority_order, routing_rule_id LIMIT 1
            """),
            {"cat": category_id},
        )
        department_id = r.scalar() or default_department_id
        if department_id is None:
            return None, None, False
        a = await self.db.execute(
            text("""
                SELECT authority_id, is_routing_placeholder FROM administration.authority
                WHERE department_id = :dep
                  AND ((jurisdiction_level = 'district' AND jurisdiction_id = :dist)
                       OR jurisdiction_level = 'state')
                ORDER BY CASE WHEN jurisdiction_level = 'district' THEN 0 ELSE 1 END,
                         is_routing_placeholder, authority_id
                LIMIT 1
            """),
            {"dep": department_id, "dist": district_id},
        )
        row = a.fetchone()
        return department_id, (row.authority_id if row else None), bool(row and row.is_routing_placeholder)

    async def _sla_hours(self, category_id, priority, department_id, default_hours):
        if category_id is None:
            return None, None
        r = await self.db.execute(
            text("""
                SELECT resolution_hours, escalation_hours FROM complaints.sla_rule
                WHERE category_id = :cat AND priority = :prio
                ORDER BY (department_id IS NOT DISTINCT FROM :dep) DESC, sla_id
                LIMIT 1
            """),
            {"cat": category_id, "prio": priority, "dep": department_id},
        )
        row = r.fetchone()
        if row:
            return row.resolution_hours, row.escalation_hours
        return default_hours, None

    # ── read ──────────────────────────────────────────────────────────────────
    async def _history(self, complaint_id) -> list[ComplaintHistoryItem]:
        hr = await self.db.execute(
            text("""
                SELECT changed_at, old_status, new_status, remarks, NULL::text AS changed_by_role
                FROM complaints.complaint_history
                WHERE complaint_id = :cid ORDER BY changed_at, history_id
            """),
            {"cid": complaint_id},
        )
        return [ComplaintHistoryItem(**dict(zip(_HISTORY_COLS, h, strict=True))) for h in hr.fetchall()]

    async def track_by_reference(self, reference: str) -> Optional[ComplaintTrack]:
        r = await self.db.execute(
            text("""
                SELECT c.complaint_id, c.complaint_ref AS reference_number, c.title, c.status,
                       cc.category_name, d.department_name, a.authority_name,
                       c.created_at, c.due_date,
                       CASE WHEN c.authority_id IS NOT NULL THEN CASE WHEN a.is_routing_placeholder THEN 'department_level' ELSE 'authority_assigned' END
                            WHEN c.department_id IS NOT NULL THEN 'department_only' ELSE 'unassigned' END AS assignment_state
                FROM complaints.complaint c
                LEFT JOIN complaints.complaint_category cc ON cc.category_id = c.category_id
                LEFT JOIN administration.department d ON d.department_id = c.department_id
                LEFT JOIN administration.authority a ON a.authority_id = c.authority_id
                WHERE c.complaint_ref = :ref AND c.is_anonymous = false
            """),
            {"ref": reference},
        )
        row = r.fetchone()
        if not row:
            return None
        return ComplaintTrack(
            reference_number=row.reference_number, title=row.title, status=row.status,
            category_name=row.category_name, department_name=row.department_name,
            authority_name=row.authority_name, created_at=row.created_at, due_date=row.due_date,
            assignment_state=row.assignment_state,
            timeline=await self._history(row.complaint_id),
            sla_breached=rules.is_sla_breached(row.due_date, row.status, datetime.now(timezone.utc)),
        )

    async def get_citizen_complaints(self, citizen_id, status, page, page_size) -> ComplaintListResponse:
        conditions = ["c.citizen_id = :cid"]
        params: dict = {"cid": citizen_id}
        if status:
            conditions.append("c.status = :status")
            params["status"] = status
        where = " AND ".join(conditions)
        cnt = await self.db.execute(
            text(f"SELECT count(*) FROM complaints.complaint c WHERE {where}"), params
        )
        total = cnt.scalar() or 0
        r = await self.db.execute(
            text(f"""
                SELECT c.complaint_id, c.complaint_ref AS reference_number, c.title, c.status,
                       cc.category_name, d.department_name, c.created_at, c.due_date,
                       CASE WHEN c.authority_id IS NOT NULL THEN CASE WHEN a.is_routing_placeholder THEN 'department_level' ELSE 'authority_assigned' END
                            WHEN c.department_id IS NOT NULL THEN 'department_only' ELSE 'unassigned' END AS assignment_state
                FROM complaints.complaint c
                LEFT JOIN complaints.complaint_category cc ON cc.category_id = c.category_id
                LEFT JOIN administration.department d ON d.department_id = c.department_id
                LEFT JOIN administration.authority a ON a.authority_id = c.authority_id
                WHERE {where}
                ORDER BY c.created_at DESC
                LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": (page - 1) * page_size},
        )
        items = [ComplaintOut(**row._mapping) for row in r.fetchall()]
        return ComplaintListResponse(
            items=items, total=total, page=page, page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_complaint(self, complaint_id: UUID, current_user) -> Optional[ComplaintDetail]:
        r = await self.db.execute(
            text("""
                SELECT c.complaint_id, c.citizen_id, c.complaint_ref AS reference_number, c.title,
                       c.description, c.status, cc.category_name, d.department_name,
                       c.latitude, c.longitude, c.address, c.priority,
                       a.authority_name, o.name AS officer_name,
                       c.created_at, c.due_date, c.escalation_due_at,
                       c.category_confidence::float AS ai_confidence, NULL::text AS ai_category,
                       CASE WHEN c.authority_id IS NOT NULL THEN CASE WHEN a.is_routing_placeholder THEN 'department_level' ELSE 'authority_assigned' END
                            WHEN c.department_id IS NOT NULL THEN 'department_only' ELSE 'unassigned' END AS assignment_state
                FROM complaints.complaint c
                LEFT JOIN complaints.complaint_category cc ON cc.category_id = c.category_id
                LEFT JOIN administration.department d ON d.department_id = c.department_id
                LEFT JOIN administration.authority a ON a.authority_id = c.authority_id
                LEFT JOIN administration.officer o ON o.officer_id = c.assigned_officer_id
                WHERE c.complaint_id = :cid
            """),
            {"cid": complaint_id},
        )
        row = r.fetchone()
        if not row:
            return None
        if not rules.can_view_complaint(
            getattr(current_user, "role", ""), getattr(current_user, "citizen_id", None), row.citizen_id
        ):
            raise ComplaintForbidden("You may only view your own complaints")
        data = dict(row._mapping)
        data.pop("citizen_id")
        detail = ComplaintDetail(**data)
        detail.timeline = await self._history(complaint_id)
        return detail

    # ── update ────────────────────────────────────────────────────────────────
    async def update_status(self, complaint_id: UUID, data: ComplaintStatusUpdate, user) -> dict:
        r = await self.db.execute(
            text("SELECT status FROM complaints.complaint WHERE complaint_id = :cid FOR UPDATE"),
            {"cid": complaint_id},
        )
        row = r.fetchone()
        if not row:
            raise ComplaintNotFound("Complaint not found")
        current = row[0]
        if data.new_status not in rules.STATUSES:
            raise ValueError(f"Unknown status '{data.new_status}'")
        if not rules.can_transition(current, data.new_status):
            raise InvalidTransition(f"Cannot transition from {current} to {data.new_status}")
        await self.db.execute(
            text("""
                UPDATE complaints.complaint
                SET status = :s,
                    resolved_at = CASE WHEN :s = 'resolved' THEN now() ELSE resolved_at END
                WHERE complaint_id = :cid
            """),
            {"s": data.new_status, "cid": complaint_id},
        )
        # trg_complaint_history just inserted the history row; annotate it.
        await self.db.execute(
            text("""
                UPDATE complaints.complaint_history
                SET remarks = :rem, changed_by = :uid
                WHERE history_id = (SELECT max(history_id) FROM complaints.complaint_history
                                    WHERE complaint_id = :cid)
            """),
            {"rem": data.remarks, "uid": getattr(user, "user_id", None), "cid": complaint_id},
        )
        await self.db.commit()
        return {"status": "updated", "new_status": data.new_status}

    async def upload_evidence(self, complaint_id: UUID, file, user) -> dict:
        allowed_types = {"image/jpeg", "image/png", "image/webp", "application/pdf",
                         "audio/mpeg", "audio/wav", "video/mp4"}
        if file.content_type not in allowed_types:
            raise ValueError(f"File type {file.content_type} not allowed")
        if file.size and file.size > 50 * 1024 * 1024:
            raise ValueError("File too large (max 50MB)")
        return {"message": "Evidence upload requires MinIO configuration", "filename": file.filename}

    async def get_categories(self) -> list:
        r = await self.db.execute(
            text("""
                SELECT category_id, category_name AS name, name_ta, description, default_priority
                FROM complaints.complaint_category
                WHERE is_active = true
                ORDER BY category_name
            """)
        )
        return [dict(row._mapping) for row in r.fetchall()]
