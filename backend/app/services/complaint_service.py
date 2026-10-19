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
from app.core.config import settings
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


class EvidenceStorageUnavailable(RuntimeError):
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
                SELECT c.complaint_id, c.citizen_id, c.department_id AS dept_id, c.complaint_ref AS reference_number, c.title,
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
        role = getattr(current_user, "role", "")
        if role in ("officer", "department_admin") and not rules.staff_can_act_on(
                role, getattr(current_user, "department_id", None), row.dept_id):
            raise ComplaintForbidden("This complaint belongs to another department")
        data = dict(row._mapping)
        data.pop("citizen_id")
        data.pop("dept_id")
        detail = ComplaintDetail(**data)
        detail.timeline = await self._history(complaint_id)
        return detail

    # ── update ────────────────────────────────────────────────────────────────
    async def update_status(self, complaint_id: UUID, data: ComplaintStatusUpdate, user) -> dict:
        r = await self.db.execute(
            text("SELECT status, department_id FROM complaints.complaint WHERE complaint_id = :cid FOR UPDATE"),
            {"cid": complaint_id},
        )
        row = r.fetchone()
        if not row:
            raise ComplaintNotFound("Complaint not found")
        current = row[0]
        if not rules.staff_can_act_on(getattr(user, "role", ""), getattr(user, "department_id", None), row[1]):
            raise ComplaintForbidden("You may only update complaints of your own department")
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

    # ── staff (officer / department admin / state admin) ──────────────────────
    @staticmethod
    def _staff_scope(user) -> Optional[int]:
        """None = every department (state/system admin); otherwise the staff member's own department id."""
        role = getattr(user, "role", "")
        if role in ("state_admin", "system_admin"):
            return None
        dept = getattr(user, "department_id", None)
        if role in ("officer", "department_admin") and dept is not None:
            return dept
        raise ComplaintForbidden("Your account is not linked to a department")

    async def list_for_staff(self, user, status: Optional[str], mine: bool, unassigned: bool,
                             limit: int, offset: int) -> dict:
        scope = self._staff_scope(user)
        cond = ["TRUE" if settings.DEMO_INCLUDE_SYNTHETIC else "NOT c.is_synthetic"]
        params: dict = {}
        if scope is not None:
            cond.append("c.department_id = :dept")
            params["dept"] = scope
        base = " AND ".join(cond)
        counts = (await self.db.execute(text(f"SELECT c.status, count(*)::int FROM complaints.complaint c WHERE {base} GROUP BY c.status"), params)).fetchall()
        flt = list(cond)
        if status:
            flt.append("c.status = :status")
            params["status"] = status
        if mine:
            flt.append("c.assigned_officer_id = :me")
            params["me"] = getattr(user, "officer_id", None)
        if unassigned:
            flt.append("c.assigned_officer_id IS NULL AND c.status NOT IN ('resolved','closed','rejected')")
        where = " AND ".join(flt)
        total = (await self.db.execute(text(f"SELECT count(*) FROM complaints.complaint c WHERE {where}"), params)).scalar() or 0
        rows = (await self.db.execute(text(f"""
            SELECT c.complaint_id::text AS complaint_id, c.complaint_ref AS reference_number, c.title, c.status, c.priority,
                   cat.category_name, d.department_name, o.name AS officer_name, c.assigned_officer_id::text AS officer_id,
                   c.created_at, c.due_date, c.is_synthetic,
                   (c.due_date < now() AND c.status NOT IN ('resolved','closed','rejected')) AS sla_breached
            FROM complaints.complaint c
            LEFT JOIN complaints.complaint_category cat ON cat.category_id = c.category_id
            LEFT JOIN administration.department d ON d.department_id = c.department_id
            LEFT JOIN administration.officer o ON o.officer_id = c.assigned_officer_id
            WHERE {where}
            ORDER BY (c.due_date < now() AND c.status NOT IN ('resolved','closed','rejected')) DESC NULLS LAST,
                     CASE c.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, c.created_at DESC
            LIMIT :lim OFFSET :off"""), {**params, "lim": limit, "off": offset})).fetchall()
        items = []
        for r in rows:
            m = dict(r._mapping)
            m["allowed_next"] = list(rules.TRANSITIONS.get(m["status"], ()))
            items.append(m)
        scope_params = {"dept": scope} if scope is not None else {}
        extra = (await self.db.execute(text(f"""
            SELECT count(*) FILTER (WHERE c.due_date < now() AND c.status NOT IN ('resolved','closed','rejected'))::int,
                   count(*) FILTER (WHERE c.assigned_officer_id IS NULL AND c.status NOT IN ('resolved','closed','rejected'))::int
            FROM complaints.complaint c WHERE {base}"""), scope_params)).fetchone()
        dept_name = None
        if scope is not None:
            dept_name = (await self.db.execute(
                text("SELECT department_name FROM administration.department WHERE department_id = :d"), {"d": scope})).scalar()
        return {"total": total, "items": items, "limit": limit, "offset": offset,
                "status_counts": {k: v for k, v in counts}, "department_scope": scope, "department_name": dept_name,
                "overdue": extra[0] if extra else 0, "unassigned": extra[1] if extra else 0,
                "demo_data_included": settings.DEMO_INCLUDE_SYNTHETIC}

    async def officers_for(self, user) -> list:
        scope = self._staff_scope(user)
        cond, params = ("WHERE o.status = 'active'" + (" AND o.department_id = :d" if scope is not None else "")), ({"d": scope} if scope is not None else {})
        r = await self.db.execute(text(f"""
            SELECT o.officer_id::text AS officer_id, o.name, o.designation, d.department_name,
                   (SELECT count(*) FROM complaints.complaint c WHERE c.assigned_officer_id = o.officer_id
                      AND c.status NOT IN ('resolved','closed','rejected'))::int AS open_complaints
            FROM administration.officer o JOIN administration.department d ON d.department_id = o.department_id
            {cond} ORDER BY d.department_name, o.name"""), params)
        return [dict(x._mapping) for x in r.fetchall()]

    async def assign(self, complaint_id: UUID, officer_id: Optional[str], user, remarks: Optional[str] = None) -> dict:
        """Assign a complaint to an officer of the complaint's department.

        Officers may only assign to themselves; department/state admins may assign to any officer of that department.
        When the state machine allows it the complaint also moves to 'assigned' (history written by the trigger).
        """
        r = await self.db.execute(
            text("SELECT status, department_id FROM complaints.complaint WHERE complaint_id = :cid FOR UPDATE"),
            {"cid": complaint_id})
        row = r.fetchone()
        if not row:
            raise ComplaintNotFound("Complaint not found")
        status, dept = row
        role = getattr(user, "role", "")
        if not rules.staff_can_act_on(role, getattr(user, "department_id", None), dept):
            raise ComplaintForbidden("You may only assign complaints of your own department")
        target = officer_id
        if role == "officer":
            target = str(getattr(user, "officer_id", "") or "")
            if officer_id and str(officer_id) != target:
                raise ComplaintForbidden("Officers may only assign complaints to themselves")
            if not target:
                raise ComplaintForbidden("Your account is not linked to an officer record")
        if not target:
            raise ValueError("officer_id is required")
        o = (await self.db.execute(
            text("SELECT department_id, name FROM administration.officer WHERE officer_id = CAST(:o AS uuid) AND status = 'active'"),
            {"o": target})).fetchone()
        if not o or o[0] != dept:
            raise ValueError("Officer not found in this complaint's department")
        await self.db.execute(
            text("UPDATE complaints.complaint SET assigned_officer_id = CAST(:o AS uuid) WHERE complaint_id = :cid"),
            {"o": target, "cid": complaint_id})
        new_status = status
        if rules.can_transition(status, "assigned"):
            new_status = "assigned"
            await self.db.execute(text("UPDATE complaints.complaint SET status = 'assigned' WHERE complaint_id = :cid"),
                                  {"cid": complaint_id})
            await self.db.execute(text("""
                UPDATE complaints.complaint_history SET remarks = :rem, changed_by = :uid
                WHERE history_id = (SELECT max(history_id) FROM complaints.complaint_history WHERE complaint_id = :cid)"""),
                {"rem": remarks or f"Assigned to {o[1]}", "uid": getattr(user, "user_id", None), "cid": complaint_id})
        await self.db.commit()
        return {"status": new_status, "assigned_officer": o[1], "officer_id": target}

    async def upload_evidence(self, complaint_id: UUID, file, user) -> dict:
        """Authorise and validate the upload. Object storage is not wired yet, so a valid upload is refused with
        EvidenceStorageUnavailable: the caller must never be told a file was saved when it was not."""
        owner = (await self.db.execute(
            text("SELECT citizen_id FROM complaints.complaint WHERE complaint_id = :cid"), {"cid": complaint_id})).fetchone()
        if owner is None:
            raise ComplaintNotFound("Complaint not found")
        if not rules.can_view_complaint(getattr(user, "role", ""), getattr(user, "citizen_id", None), owner.citizen_id):
            raise ComplaintForbidden("You may only add evidence to your own complaints")
        allowed_types = {"image/jpeg", "image/png", "image/webp", "application/pdf",
                         "audio/mpeg", "audio/wav", "video/mp4"}
        if file.content_type not in allowed_types:
            raise ValueError(f"File type {file.content_type} not allowed")
        if file.size and file.size > 50 * 1024 * 1024:
            raise ValueError("File too large (max 50MB)")
        raise EvidenceStorageUnavailable("Evidence storage is not configured on this server; your file was NOT saved.")

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
