from __future__ import annotations

import json
from pathlib import Path

from analysis.eval.efficiency import overlay_row, propose_thresholds, reviewer_valid
from analysis.eval.runner import load_golden, run_suite
from analysis.graph import run_investigation

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "evals" / "golden.json"
OLIST_RUBRIC = ROOT / "evals" / "olist_rubric.json"
ADVERSARIAL = ROOT / "evals" / "adversarial.json"
FIXTURES = ROOT / "data" / "fixtures"


def test_catalogs_unchanged_shape():
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(golden["items"]) == 21
    assert all("expected" in i for i in golden["items"])
    olist = json.loads(OLIST_RUBRIC.read_text(encoding="utf-8"))
    assert [i["id"] for i in olist["items"]] == ["ol-delay-review", "ol-gmv-review-category"]
    adv = json.loads(ADVERSARIAL.read_text(encoding="utf-8"))
    assert len(adv["items"]) == 7


def test_cheap_wrong_answer_is_blocked_not_efficient():
    result = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    row = overlay_row(
        case="fake-wrong",
        suite="golden",
        correct=False,
        evidence_valid=True,
        result=result,
        extra={"metric_type": "driver"},
    )
    assert row["efficiency"] == "blocked"
    assert row["block_reason"] == "correctness"
    assert row["efficiency_eligible"] is False
    assert row["experiments"] >= 1


def test_reviewer_valid_on_golden_driver():
    result = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    assert reviewer_valid(result) is True


def test_efficiency_does_not_fail_golden_suite():
    report = run_suite()
    assert report["pass"]
    row = next(i for i in report["items"] if i["id"] == "ev-d1")
    assert "total_tool_calls" in row["efficiency"]
    assert "hypotheses_executed" in row["efficiency"]
    assert row["efficiency_row"]["correct"] is True
    assert row["gates"]["correctness"] is True


def test_proposed_threshold_matches_measured_max_not_a_guess():
    report = run_suite()
    rows = [i["efficiency_row"] for i in report["items"] if i.get("efficiency_row")]
    proposal = propose_thresholds(rows)
    assert proposal["enforced"] is False
    eligible = [r for r in rows if r["efficiency_eligible"] and r["case"] != "ev-b1"]
    assert proposal["experiments"]["proposed_max"] == max(r["experiments"] for r in eligible)
    assert proposal["tool_calls"]["proposed_max"] == max(r["tool_calls"] for r in eligible)
    assert load_golden()[0]["id"] == "ev-d1"
