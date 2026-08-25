from __future__ import annotations

from collections import Counter
from pathlib import Path

from analysis.eval.runner import hallucination_is_caught, load_golden, run_suite

ROOT = Path(__file__).resolve().parents[1]


def test_golden_matrix_shape():
    items = load_golden()
    counts = Counter(i["metric_type"] for i in items if i["id"] != "ev-b1")
    assert counts["driver"] == 5
    assert counts["trap"] == 3
    assert counts["abstain"] == 3
    assert counts["interaction"] == 3
    assert counts["temporal"] == 2
    assert counts["anomaly"] == 2
    assert counts["numerical"] == 2
    assert any(i["id"] == "ev-b1" for i in items)


def test_eval_suite_gates_pass():
    report = run_suite()
    failed = [r for r in report["items"] if not r.get("skipped") and not r["pass"]]
    assert report["pass"], failed
    types = {r["id"]: r for r in report["items"]}
    assert types["ev-a1"]["stop_reason"] == "abstain"
    assert types["ev-a2"]["decision"] == "abstain"
    assert types["ev-b1"]["stop_reason"] == "budget"
    assert report["efficiency_log"]
    assert all("duration_ms" in row for row in report["efficiency_log"])


def test_eval_hallucinated_number_fails_lock():
    assert hallucination_is_caught() is True
