from __future__ import annotations

from pathlib import Path

from analysis.eval.adaptive import run_adaptive
from analysis.graph import run_investigation
from analysis.tools.schemas import CLOSED_TEMPLATES, Budget, V1_TOOLS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def test_adaptive_does_not_add_tools_or_python():
    assert "run_python" not in V1_TOOLS
    assert "review_claims" not in V1_TOOLS


def test_unique_driver_does_not_enter_next_research():
    out = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    assert out["decision"] == "primary_driver"
    assert out["primary_driver"] == "West × Office Supplies"
    assert out["stop_reason"] == "strong_evidence"
    assert "assess_evidence" in out["plan"]
    assert "next_research" not in out["plan"]
    assert out["research_steps"] == []
    assert "review_claims" in out["plan"]
    assert all(h["template_id"] in CLOSED_TEMPLATES for h in out["hypotheses"])


def test_competing_drivers_adapt_then_abstain():
    out = run_investigation(
        FIXTURES / "adaptive" / "competing_drivers.csv",
        "What drove the sales change?",
    )
    assert out["hypotheses"][0]["template_id"] == "data_artefact"
    tested = [h for h in out["hypotheses"] if h["status"] == "tested"]
    assert tested[0]["template_id"] == "data_artefact"
    assert "next_research" in out["plan"]
    assert out["research_steps"]
    assert "unique primary driver" in out["research_steps"][0]["reason"].lower()
    assert out["research_steps"][0]["template_id"] in CLOSED_TEMPLATES
    assert out["decision"] == "abstain"
    assert out["primary_driver"] is None
    assert out["insufficient_kind"] == "multiple_plausible_drivers"
    assert out["claims"]
    assert out["claims"][0]["kind"] == "abstention"
    assert out["reviews"]
    assert "cause" not in out["claims"][0]["text"].lower()


def test_budget_exhaustion_abstains():
    out = run_investigation(
        FIXTURES / "adaptive" / "competing_drivers.csv",
        "What drove the sales change?",
        budget=Budget(max_experiments=7, max_seconds=60),
    )
    assert out["stop_reason"] == "budget"
    assert out["decision"] == "abstain"
    assert out["primary_driver"] is None
    assert "review_claims" in out["plan"]


def test_adaptive_eval_suite_passes():
    report = run_adaptive()
    failed = [r["id"] for r in report["items"] if not r["pass"]]
    assert report["pass"], failed
