"""Complaint service — submission, classification, routing, SLA."""
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.complaints import (
    ComplaintCreate, ComplaintOut, ComplaintDetail, ComplaintListResponse,
    ComplaintStatusUpdate, ComplaintTrack, ComplaintHistoryItem,
)

logger = structlog.get_logger(__name__)

# Valid status transitions
_TRANSITIONS: dict[str, list[str]] = {
    "submitted":     ["classified", "needs_triage", "rejected"],
    "needs_triage":  ["classified"],
    "classified":    ["assigned", "rejected"],
    "assigned":      ["in_progress", "escalated", "rejected"],
    "in_progress":   ["resolved", "escalated"],
    "escalated":     ["in_progress", "resolved"],
    "resolved":      ["closed", "reopened"],
    "reopened":      ["in_progress"],
    "closed":        [],
    "rejected":      [],
}


def _generate_reference(complaint_id: UUID) -> str:
    year = datetime.now(timezone.utc).year
    seq = int(str(complaint_id.int)[-6:]) % 999999 + 1
    return f"MYG-{year}-{seq:06d}"


class ComplaintService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(self, data: ComplaintCreate, user_id: str) -> ComplaintOut:
        # Get citizen_id from user
        u = await self.db.execute(
            text("SELECT citizen_id FROM identity.app_user WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        citizen_id = u.scalar()

        complaint_id = uuid4()
        reference = _generate_reference(complaint_id)

        # Basic AI classification stub (deterministic fallback)
        category_id = data.category_id
        priority = "medium"
        ai_confidence = 0.0
        ai_category = None

        if category_id:
            cr = await self.db.execute(
                text("SELECT default_priority FROM complaints.complaint_category WHERE category_id = :cid"),
                {"cid": str(category_id)},
            )
            row = cr.fetchone()
            if row:
                priority = row[0]
            ai_confidence = 1.0

        # Jurisdiction resolution
        ward_id = None
        local_body_id = None
        taluk_id = None
        district_id = data.district_id

        if data.latitude and data.longitude:
            try:
                jr = await self.db.execute(
                    text("SELECT ward_id, local_body_id, taluk_id, district_id FROM administration.resolve_jurisdiction(:lon, :lat)"),
                    {"lon": data.longitude, "lat": data.latitude},
                )
                jrow = jr.fetchone()
                if jrow:
                    ward_id, local_body_id, taluk_id, district_id = jrow
            except Exception as e:
                logger.warning("Jurisdiction resolution failed", error=str(e))

        # Routing rule lookup
        authority_id = await self._route_complaint(category_id, district_id, local_body_id)

        # SLA calculation
        sla_hours = 72  # default
        escalation_hours = 48
        if category_id:
            sr = await self.db.execute(
                text("""
                    SELECT resolution_hours, escalation_hours
                    FROM complaints.sla_rule
                    WHERE category_id = :cid AND is_active = true
                    LIMIT 1
                """),
                {"cid": str(category_id)},
            )
            srow = sr.fetchone()
            if srow:
                sla_hours, escalation_hours = srow

        now = datetime.now(timezone.utc)
        due_date = now + timedelta(hours=sla_hours)
        escalation_due_at = now + timedelta(hours=escalation_hours)
        status = "classified" if ai_confidence >= 0.6 else "needs_triage"

        # Insert complaint
        await self.db.execute(
            text("""
                INSERT INTO complaints.complaint (
                    complaint_id, citizen_id, reference_number, title, description,
                    category_id, status, priority, latitude, longitude, address,
                    ward_id, local_body_id, taluk_id, district_id,
                    authority_id, due_date, escalation_due_at,
                    ai_confidence, ai_category, is_anonymous, created_at, updated_at
                ) VALUES (
                    :cid, :citizen_id, :ref, :title, :desc,
                    :cat_id, :status, :priority, :lat, :lon, :addr,
                    :ward_id, :lb_id, :taluk_id, :dist_id,
                    :auth_id, :due_date, :esc_due_at,
                    :ai_conf, :ai_cat, :anon, now(), now()
                )
            """),
            {
                "cid": str(complaint_id), "citizen_id": str(citizen_id) if citizen_id else None,
                "ref": reference, "title": data.title, "desc": data.description,
                "cat_id": str(category_id) if category_id else None,
                "status": status, "priority": priority,
                "lat": data.latitude, "lon": data.longitude, "addr": data.address,
                "ward_id": ward_id, "lb_id": local_body_id, "taluk_id": taluk_id,
                "dist_id": district_id, "auth_id": str(authority_id) if authority_id else None,
                "due_date": due_date, "esc_due_at": escalation_due_at,
                "ai_conf": ai_confidence, "ai_cat": ai_category, "anon": data.is_anonymous,
            },
        )

        # Insert initial history row
        await self.db.execute(
            text("""
                INSERT INTO complaints.complaint_history (complaint_id, old_status, new_status, remarks, changed_at)
                VALUES (:cid, NULL, :status, 'Complaint submitted', now())
            """),
            {"cid": str(complaint_id), "status": status},
        )

        await self.db.commit()

        # Fetch category name
        cat_name = None
        if category_id:
            cnr = await self.db.execute(
                text("SELECT name FROM complaints.complaint_category WHERE category_id = :cid"),
                {"cid": str(category_id)},
            )
            cat_name = cnr.scalar()

        return ComplaintOut(
            complaint_id=complaint_id,
            reference_number=reference,
            title=data.title,
            status=status,
            category_name=cat_name,
            created_at=now,
            due_date=due_date,
        )

    async def _route_complaint(self, category_id, district_id, local_body_id) -> Optional[UUID]:
        if not category_id:
            return None
        try:
            r = await self.db.execute(
                text("""
                    SELECT a.authority_id
                    FROM complaints.routing_rule rr
                    JOIN administration.authority a ON a.department_id = rr.department_id
                    WHERE rr.category_id = :cat_id
                    LIMIT 1
                """),
                {"cat_id": str(category_id)},
            )
            row = r.fetchone()
            return row[0] if row else None
        except Exception:
            return None

    async def track_by_reference(self, reference: str) -> Optional[ComplaintTrack]:
        r = await self.db.execute(
            text("""
                SELECT c.complaint_id, c.reference_number, c.title, c.status,
                       cc.name AS category_name, d.department_name,
                       a.authority_name, c.created_at, c.due_date,
                       (c.due_date < now() AND c.status NOT IN ('resolved','closed')) AS sla_breached
                FROM complaints.complaint c
                LEFT JOIN complaints.complaint_category cc ON cc.category_id = c.category_id
                LEFT JOIN administration.authority a ON a.authority_id = c.authority_id
                LEFT JOIN administration.department d ON d.department_id = a.department_id
                WHERE c.reference_number = :ref AND c.is_anonymous = false
            """),
            {"ref": reference},
        )
        row = r.fetchone()
        if not row:
            return None

        cols = list(r.keys())
        data = dict(zip(cols, row))
        complaint_id = data["complaint_id"]

        # History
        hr = await self.db.execute(
            text("""
                SELECT changed_at, old_status, new_status, remarks, NULL AS changed_by_role
                FROM complaints.complaint_history
                WHERE complaint_id = :cid ORDER BY changed_at
            """),
            {"cid": str(complaint_id)},
        )
        history = [
            ComplaintHistoryItem(**dict(zip(["changed_at","old_status","new_status","remarks","changed_by_role"], h)))
            for h in hr.fetchall()
        ]

        return ComplaintTrack(
            reference_number=data["reference_number"],
            title=data["title"],
            status=data["status"],
            category_name=data.get("category_name"),
            department_name=data.get("department_name"),
            authority_name=data.get("authority_name"),
            created_at=data["created_at"],
            due_date=data.get("due_date"),
            timeline=history,
            sla_breached=bool(data.get("sla_breached")),
        )

    async def get_citizen_complaints(self, citizen_id, status, page, page_size) -> ComplaintListResponse:
        conditions = ["c.citizen_id = :cid"]
        params: dict = {"cid": str(citizen_id)}
        if status:
            conditions.append("c.status = :status")
            params["status"] = status
        where = " AND ".join(conditions)

        cnt = await self.db.execute(
            text(f"SELECT count(*) FROM complaints.complaint c WHERE {where}"), params
        )
        total = cnt.scalar() or 0

        offset = (page - 1) * page_size
        r = await self.db.execute(
            text(f"""
                SELECT c.complaint_id, c.reference_number, c.title, c.status,
                       cc.name AS category_name, d.department_name,
                       c.created_at, c.due_date
                FROM complaints.complaint c
                LEFT JOIN complaints.complaint_category cc ON cc.category_id = c.category_id
                LEFT JOIN administration.authority a ON a.authority_id = c.authority_id
                LEFT JOIN administration.department d ON d.department_id = a.department_id
                WHERE {where}
                ORDER BY c.created_at DESC
                LIMIT :lim OFFSET :off
            """),
            {**params, "lim": page_size, "off": offset},
        )
        cols = list(r.keys())
        items = [ComplaintOut(**dict(zip(cols, row))) for row in r.fetchall()]
        return ComplaintListResponse(
            items=items, total=total, page=page, page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_complaint(self, complaint_id: UUID, current_user) -> Optional[ComplaintDetail]:
        r = await self.db.execute(
            text("""
                SELECT c.complaint_id, c.reference_number, c.title, c.description,
                       c.status, cc.name AS category_name, d.department_name,
                       c.latitude, c.longitude, c.address, c.priority,
                       a.authority_name, NULL AS officer_name,
                       c.created_at, c.due_date, c.escalation_due_at,
                       c.ai_confidence, c.ai_category
                FROM complaints.complaint c
                LEFT JOIN complaints.complaint_category cc ON cc.category_id = c.category_id
                LEFT JOIN administration.authority a ON a.authority_id = c.authority_id
                LEFT JOIN administration.department d ON d.department_id = a.department_id
                WHERE c.complaint_id = :cid
            """),
            {"cid": str(complaint_id)},
        )
        row = r.fetchone()
        if not row:
            return None

        data = dict(zip(r.keys(), row))

        # History
        hr = await self.db.execute(
            text("""
                SELECT changed_at, old_status, new_status, remarks, NULL AS changed_by_role
                FROM complaints.complaint_history
                WHERE complaint_id = :cid ORDER BY changed_at
            """),
            {"cid": str(complaint_id)},
        )
        history = [
            ComplaintHistoryItem(**dict(zip(["changed_at","old_status","new_status","remarks","changed_by_role"], h)))
            for h in hr.fetchall()
        ]

        detail = ComplaintDetail(**{k: v for k, v in data.items() if k in ComplaintDetail.model_fields})
        detail.timeline = history
        return detail

    async def update_status(self, complaint_id: UUID, data: ComplaintStatusUpdate, user) -> dict:
        r = await self.db.execute(
            text("SELECT status FROM complaints.complaint WHERE complaint_id = :cid FOR UPDATE"),
            {"cid": str(complaint_id)},
        )
        row = r.fetchone()
        if not row:
            raise ValueError("Complaint not found")

        current_status = row[0]
        allowed = _TRANSITIONS.get(current_status, [])
        if data.new_status not in allowed:
            raise ValueError(f"Cannot transition from {current_status} to {data.new_status}")

        await self.db.execute(
            text("UPDATE complaints.complaint SET status = :s, updated_at = now() WHERE complaint_id = :cid"),
            {"s": data.new_status, "cid": str(complaint_id)},
        )
        await self.db.execute(
            text("""
                INSERT INTO complaints.complaint_history (complaint_id, old_status, new_status, remarks, changed_at)
                VALUES (:cid, :old, :new, :rem, now())
            """),
            {"cid": str(complaint_id), "old": current_status, "new": data.new_status, "rem": data.remarks},
        )
        await self.db.commit()
        return {"status": "updated", "new_status": data.new_status}

    async def upload_evidence(self, complaint_id: UUID, file, user) -> dict:
        # Validate MIME
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
                SELECT category_id, name, name_ta, description, default_priority
                FROM complaints.complaint_category
                WHERE is_active = true
                ORDER BY name
            """)
        )
        cols = list(r.keys())
        return [dict(zip(cols, row)) for row in r.fetchall()]
