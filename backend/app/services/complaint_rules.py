"""Pure complaint business rules (no I/O) - state machine, SLA deadlines, access control.

Statuses mirror the CHECK constraint on complaints.complaint.status in 001_schema.sql.
"""
from __future__ import annotations

from datetime import datetime, timedelta

STATUSES = frozenset({
    "submitted", "needs_triage", "classified", "assigned", "in_progress",
    "resolved", "closed", "rejected", "escalated", "reopened",
})

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "submitted":    ("classified", "needs_triage", "rejected"),
    "needs_triage": ("classified",),
    "classified":   ("assigned", "rejected"),
    "assigned":     ("in_progress", "escalated", "rejected"),
    "in_progress":  ("resolved", "escalated"),
    "escalated":    ("in_progress", "resolved"),
    "resolved":     ("closed", "reopened"),
    "reopened":     ("in_progress",),
    "closed":       (),
    "rejected":     (),
}

TERMINAL = frozenset(s for s, nxt in TRANSITIONS.items() if not nxt)
# Statuses from which the SLA scheduler may escalate (i.e. escalated is a legal next state).
ESCALATABLE = tuple(sorted(s for s, nxt in TRANSITIONS.items() if "escalated" in nxt))

STAFF_ROLES = frozenset({"officer", "department_admin", "state_admin", "system_admin"})
DEFAULT_RESOLUTION_HOURS = 72
DEFAULT_ESCALATION_HOURS = 48


def assignment_state(authority_id, authority_is_placeholder: bool, department_id) -> str:
    """How far routing got - reported to citizens so an unrouted complaint is never hidden.

    authority_assigned : routed to a (non-placeholder) authority
    department_level   : routed to the department's platform routing target (no specific office yet)
    department_only    : a department was identified but no authority exists for it
    unassigned         : no department or authority (e.g. awaiting triage)
    """
    if authority_id is not None:
        return "department_level" if authority_is_placeholder else "authority_assigned"
    return "department_only" if department_id is not None else "unassigned"


def can_transition(old: str, new: str) -> bool:
    return new in TRANSITIONS.get(old, ())


def initial_status(has_category: bool) -> str:
    """A complaint with an explicit category is routable; otherwise it needs manual triage."""
    return "classified" if has_category else "needs_triage"


def compute_deadlines(
    now: datetime, resolution_hours: int | None, escalation_hours: int | None
) -> tuple[datetime, datetime]:
    """(due_date, escalation_due_at). Escalation never falls after the resolution deadline."""
    res = resolution_hours if resolution_hours and resolution_hours > 0 else DEFAULT_RESOLUTION_HOURS
    esc = escalation_hours if escalation_hours and escalation_hours > 0 else DEFAULT_ESCALATION_HOURS
    esc = min(esc, res)
    return now + timedelta(hours=res), now + timedelta(hours=esc)


def is_sla_breached(due_date: datetime | None, status: str, now: datetime) -> bool:
    return due_date is not None and due_date < now and status not in ("resolved", "closed", "rejected")


def can_view_complaint(role: str, user_citizen_id, complaint_citizen_id) -> bool:
    """Staff may read any complaint; citizens only their own."""
    if role in STAFF_ROLES:
        return True
    return user_citizen_id is not None and str(user_citizen_id) == str(complaint_citizen_id)
