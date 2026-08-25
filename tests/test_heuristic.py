from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from analysis.evidence.log import EvidenceLog
from analysis.heuristic import run_heuristic
from analysis.load import load_tabular
from analysis.tools.runtime import ToolContext, call_tool
from analysis.tools.schemas import CLOSED_TEMPLATES, Budget, V1_TOOLS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"
SUPERSTORE = ROOT / "data" / "raw" / "superstore.csv"


def _expected(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.expected.json").read_text(encoding="utf-8"))


def test_v1_tools_do_not_include_run_python():
    assert "run_python" not in V1_TOOLS
    assert "inspect_dataset" in V1_TOOLS


def test_clear_driver_via_heuristic():
    exp = _expected("clear_driver")
    out = run_heuristic(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    assert out["primary_driver"] == exp["primary_driver"]
    assert out["decision"] == "primary_driver"
    assert out["stop_reason"] == "strong_evidence"
    assert "inspect_dataset" in out["plan"]
    assert "detect_capabilities" in out["plan"]
    assert out["claims"]
    assert out["claims"][0]["kind"] == "association"
    assert "cause" not in out["claims"][0]["text"].lower()
    assert out["traces"]
    assert all("tool" in t and "duration_ms" in t for t in out["traces"])
    assert out["hypotheses"]


def test_no_signal_heuristic_abstains():
    out = run_heuristic(FIXTURES / "no_signal.csv", "Satış neden değişti?")
    assert out["decision"] == "abstain"
    assert out["primary_driver"] is None
    assert out["stop_reason"] == "abstain"
    kinds = {c["kind"] for c in out["claims"]}
    assert kinds <= {"abstention"}


def test_aov_trap_heuristic():
    out = run_heuristic(FIXTURES / "aov_trap.csv", "Satış neden değişti?")
    assert out["decision"] == "value_not_volume"
    assert out["primary_driver"] == "AOV"


def test_missingness_heuristic_artefact():
    out = run_heuristic(FIXTURES / "missingness.csv", "Satış neden değişti?")
    assert out["decision"] == "data_artefact"
    assert out["primary_driver"] is None


def test_delivery_question_abstains_without_hypotheses():
    out = run_heuristic(FIXTURES / "clear_driver.csv", "Teslimat gecikmesi puanı nasıl etkiler?")
    assert out["stop_reason"] == "abstain"
    assert out["hypotheses"] == []
    assert out["decision"] == "abstain"


@pytest.mark.skipif(not SUPERSTORE.exists(), reason="superstore.csv is local-only")
def test_superstore_delivery_abstains():
    out = run_heuristic(SUPERSTORE, "What is the effect of delivery delay on satisfaction?")
    assert out["stop_reason"] == "abstain"
    assert out["hypotheses"] == []
    assert out["capabilities"].get("delivery_analysis") is False


def test_run_sql_select_only():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    ctx = ToolContext(df=df, log=EvidenceLog())
    ok = call_tool(ctx, "run_sql", sql="SELECT region, SUM(sales) AS s FROM df GROUP BY region")
    assert ok.ok
    bad = call_tool(ctx, "run_sql", sql="DELETE FROM df")
    assert not bad.ok
    assert "SELECT" in bad.error


def test_budget_stop_does_not_crash():
    out = run_heuristic(
        FIXTURES / "clear_driver.csv",
        "Satış neden değişti?",
        budget=Budget(max_experiments=1, max_hypotheses=8, max_seconds=60),
    )
    assert out["stop_reason"] == "budget"
    assert out["budget"]["experiments_used"] >= 1


def test_missing_date_error_is_explicit():
    df = pd.DataFrame({"sales": [1.0, 2.0], "region": ["A", "B"]})
    ctx = ToolContext(df=df, log=EvidenceLog())
    err = call_tool(ctx, "compare_periods")
    assert not err.ok
    assert "date" in err.error.lower() or "time" in err.error.lower()


def test_empty_dimension_error():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    ctx = ToolContext(df=df, log=EvidenceLog())
    err = call_tool(ctx, "segment_by", dimensions=["not_a_column"])
    assert not err.ok
    assert "empty column" in err.error.lower() or "not in dataset" in err.error.lower()


def test_rank_uses_only_closed_templates():
    out = run_heuristic(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    ids = {h["template_id"] for h in out["hypotheses"]}
    assert ids <= CLOSED_TEMPLATES


def test_abstain_does_not_claim_worst_region():
    out = run_heuristic(FIXTURES / "no_signal.csv", "Satış neden değişti?")
    assert out["primary_driver"] is None
    assert out["charts"] == []
    blob = json.dumps(out["claims"], ensure_ascii=False)
    assert "West ×" not in blob
    delivery = run_heuristic(FIXTURES / "clear_driver.csv", "Teslimat gecikmesi nedir?")
    assert delivery["hypotheses"] == []
    assert "test_hypothesis" not in delivery["plan"]


def test_tool_ok_does_not_return_dataframe():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    ctx = ToolContext(df=df, log=EvidenceLog())
    ok = call_tool(ctx, "inspect_dataset")
    assert ok.ok
    assert not any(isinstance(v, pd.DataFrame) for v in ok.extra.values())
    json.dumps(ok.model_dump())
    assert ok.evidence_ids

