"""Complaint state machine, SLA deadlines, escalation thresholds, access rules."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services import complaint_rules as r

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
SCHEMA = Path(__file__).resolve().parents[3] / "database" / "schema" / "001_schema.sql"


def test_statuses_match_database_check_constraint():
    sql = SCHEMA.read_text(encoding="utf-8")
    block = re.search(r"status\s+text NOT NULL DEFAULT 'submitted' CHECK \(status IN\s*\((.*?)\)\)", sql, re.S).group(1)
    assert set(re.findall(r"'(\w+)'", block)) == set(r.STATUSES)


def test_transition_table_is_closed_over_known_statuses():
    assert set(r.TRANSITIONS) == set(r.STATUSES)
    for targets in r.TRANSITIONS.values():
        assert set(targets) <= r.STATUSES


@pytest.mark.parametrize("old,new", [
    ("submitted", "classified"), ("classified", "assigned"), ("assigned", "in_progress"),
    ("in_progress", "resolved"), ("resolved", "closed"), ("resolved", "reopened"),
    ("reopened", "in_progress"), ("escalated", "resolved"), ("assigned", "escalated"),
])
def test_legal_transitions(old, new):
    assert r.can_transition(old, new)


@pytest.mark.parametrize("old,new", [
    ("submitted", "resolved"), ("closed", "reopened"), ("rejected", "classified"),
    ("resolved", "in_progress"), ("submitted", "submitted"), ("classified", "escalated"),
    ("nonsense", "closed"),
])
def test_illegal_transitions(old, new):
    assert not r.can_transition(old, new)


def test_terminal_states_have_no_exit():
    assert {"closed", "rejected"} == r.TERMINAL


def test_escalatable_statuses_are_exactly_those_that_may_escalate():
    assert set(r.ESCALATABLE) == {"assigned", "in_progress"}
    assert all(r.can_transition(s, "escalated") for s in r.ESCALATABLE)


def test_initial_status_depends_on_category():
    assert r.initial_status(True) == "classified" and r.initial_status(False) == "needs_triage"


def test_deadlines_use_rule_hours():
    due, esc = r.compute_deadlines(NOW, 24, 12)
    assert due == NOW + timedelta(hours=24) and esc == NOW + timedelta(hours=12)


@pytest.mark.parametrize("res,esc", [(None, None), (0, 0), (-5, -1)])
def test_deadlines_fall_back_to_defaults(res, esc):
    due, e = r.compute_deadlines(NOW, res, esc)
    assert due == NOW + timedelta(hours=72) and e == NOW + timedelta(hours=48)


def test_escalation_never_after_resolution_deadline():
    due, esc = r.compute_deadlines(NOW, 10, 48)
    assert esc <= due


def test_sla_breach_flag():
    past, future = NOW - timedelta(hours=1), NOW + timedelta(hours=1)
    assert r.is_sla_breached(past, "in_progress", NOW)
    assert not r.is_sla_breached(future, "in_progress", NOW)
    assert not r.is_sla_breached(past, "resolved", NOW)
    assert not r.is_sla_breached(None, "assigned", NOW)


def test_view_access():
    assert r.can_view_complaint("officer", None, "c1")
    assert r.can_view_complaint("citizen", "c1", "c1")
    assert not r.can_view_complaint("citizen", "c2", "c1")
    assert not r.can_view_complaint("citizen", None, "c1")
