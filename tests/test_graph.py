from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis.graph import run_investigation
from analysis.heuristic import run_heuristic
from analysis.policy import UnknownTemplateError, apply_llm_rank
from analysis.tools.schemas import CLOSED_TEMPLATES, Budget

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def _expected(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.expected.json").read_text(encoding="utf-8"))


def test_unknown_template_fails():
    roles = [{"name": "region", "role": "dimension"}]
    with pytest.raises(UnknownTemplateError):
        apply_llm_rank(
            [{"template_id": "invented_operator", "bindings": {}}],
            roles,
            Budget(),
        )


def test_heuristic_and_allowlisted_llm_same_clear_driver():
    exp = _expected("clear_driver")
    path = FIXTURES / "clear_driver.csv"
    q = "Satış neden değişti?"
    off = run_investigation(path, q, policy="heuristic")
    hyps = off["hypotheses"]
    assert all(h["template_id"] in CLOSED_TEMPLATES for h in hyps)
    on = run_investigation(path, q, policy="llm", llm_rank=hyps)
    assert off["primary_driver"] == on["primary_driver"] == exp["primary_driver"]
    assert off["decision"] == on["decision"] == "primary_driver"
    assert "cause" not in json.dumps(on["claims"]).lower()
    assert "rank_hypotheses" in on["plan"]
    assert "intersect" in on["plan"]
    assert on["stop_reason"] == "strong_evidence"


def test_llm_unknown_template_fails_the_run():
    with pytest.raises(UnknownTemplateError):
        run_investigation(
            FIXTURES / "clear_driver.csv",
            "Satış neden değişti?",
            policy="llm",
            llm_rank=[{"template_id": "calculate_monthly_sales", "bindings": {}}],
        )


def test_graph_no_signal_and_delivery_abstain():
    quiet = run_investigation(FIXTURES / "no_signal.csv", "Satış neden değişti?")
    assert quiet["decision"] == "abstain"
    delivery = run_investigation(
        FIXTURES / "clear_driver.csv", "Teslimat gecikmesi puanı nasıl etkiler?"
    )
    assert delivery["hypotheses"] == []
    assert delivery["stop_reason"] == "abstain"
    assert "experiment_loop" not in delivery["plan"]


def test_ranking_intent_shortens_loop_but_keeps_evidence():
    why = run_heuristic(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    rank = run_investigation(FIXTURES / "clear_driver.csv", "Hangi bölge en yüksek?")
    assert rank["decision"] == "ranking"
    assert len(rank["hypotheses"]) < len(why["hypotheses"])
    assert all(h["template_id"] == "segment_driver" for h in rank["hypotheses"])
    assert rank["claims"]
    assert rank["claims"][0]["kind"] == "ranking"
    assert rank["claims"][0]["evidence_ids"]
    assert rank["claims"][0]["provenance_ok"] is True


def test_budget_stop_reason_on_graph():
    out = run_investigation(
        FIXTURES / "clear_driver.csv",
        "Satış neden değişti?",
        budget=Budget(max_experiments=1, max_seconds=60),
    )
    assert out["stop_reason"] == "budget"
