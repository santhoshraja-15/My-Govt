"""Retrieval-evaluation harness and the one-shot SLA job."""
import json

import pytest

from ai.eval import run_all as ev
from app.ai.embeddings.providers import DeterministicTestProvider
from app.jobs import sla_once


def test_score_computes_hit_top1_and_abstention():
    cases = [
        {"question": "a", "expect": "answer", "titles_any": ["Breakfast"]},
        {"question": "b", "expect": "answer", "titles_any": ["Nativity"]},
        {"question": "c", "expect": "abstain"},
        {"question": "d", "expect": "abstain"},
    ]
    results = [
        {"abstained": False, "titles": ["Chief Minister Breakfast Scheme"]},                # hit, top-1
        {"abstained": False, "titles": ["Income Certificate", "Nativity Certificate"]},     # hit but not top-1
        {"abstained": True, "titles": []},                                                  # correct refusal
        {"abstained": False, "titles": ["Something"]},                                      # should have refused
    ]
    m = ev.score(cases, results)
    assert (m["hit_rate"], m["top1_rate"], m["abstain_accuracy"]) == (1.0, 0.5, 0.5)
    assert m["failures"] == ["d"]


def test_score_rejects_misaligned_inputs():
    with pytest.raises(ValueError):
        ev.score([{"question": "a", "expect": "abstain"}], [])


def test_golden_cases_are_well_formed():
    cases = json.loads(ev.CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 10
    for c in cases:
        assert c["expect"] in ("answer", "abstain") and c["question"].strip()
        assert (c["expect"] == "abstain") or c["titles_any"]
    assert sum(c["expect"] == "abstain" for c in cases) >= 3


@pytest.mark.db
async def test_evaluate_runs_the_real_retrieval_over_the_seeded_catalogue(session_factory):
    cases = [
        {"question": "Tell me about the Chief Minister breakfast scheme for school children", "expect": "answer", "titles_any": ["Breakfast"]},
        {"question": "How can I apply for a smart ration card?", "expect": "answer", "titles_any": ["Ration Card"]},
        {"question": "How do I bake a chocolate cake?", "expect": "abstain"},
    ]
    m = await ev.evaluate(session_factory, cases, DeterministicTestProvider())
    assert m["hit_rate"] == 1.0 and m["abstain_accuracy"] == 1.0 and m["failures"] == []


async def test_sla_once_reports_success_and_failure(monkeypatch, capsys):
    async def ok():
        return 3

    async def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(sla_once, "escalate_overdue_complaints", ok)
    assert await sla_once.main() == 0 and "escalated 3" in capsys.readouterr().out
    monkeypatch.setattr(sla_once, "escalate_overdue_complaints", boom)
    assert await sla_once.main() == 1 and "db down" in capsys.readouterr().err
