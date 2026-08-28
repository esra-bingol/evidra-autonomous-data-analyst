from __future__ import annotations

import csv
import json
from pathlib import Path

from analysis.eval.adversarial import load_catalog, run_adversarial

ROOT = Path(__file__).resolve().parents[1]
ADV = ROOT / "data" / "fixtures" / "adversarial"
REQUIRED_CATEGORIES = {
    "correlation_not_causation",
    "causal_claim_trap",
    "simpsons_paradox",
    "outlier_mean_distortion",
    "multiple_plausible_drivers",
    "misleading_aggregate",
    "insufficient_evidence_missing_capability",
}
REQUIRED_FIELDS = (
    "category",
    "expected_behavior",
    "actual_behavior",
    "pass",
    "failure_reason",
)


def test_adversarial_catalog_covers_required_categories():
    cats = {item["category"] for item in load_catalog()}
    assert REQUIRED_CATEGORIES <= cats


def test_adversarial_fixtures_are_small_and_documented():
    for item in load_catalog():
        csv_path = ROOT / item["dataset"]
        assert csv_path.exists(), csv_path
        with csv_path.open(encoding="utf-8") as fh:
            n = sum(1 for _ in csv.DictReader(fh))
        assert 1 <= n <= 24, (item["id"], n)
        sidecar = csv_path.with_name(csv_path.name.replace(".csv", ".expected.json"))
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["category"] == item["category"]
        assert payload["why_adversarial"]
        assert payload["ground_truth"]
        assert payload["expected_analytic_behavior"]
        assert payload["expected_claim_reviewer_behavior"]


def test_adversarial_report_schema_and_must_pass_locks():
    report = run_adversarial()
    assert report["n_items"] >= 7
    for row in report["items"]:
        for key in REQUIRED_FIELDS:
            assert key in row, key
        assert "decision" in row["actual_behavior"]
        if row["must_pass"]:
            assert row["pass"], {
                "id": row["id"],
                "failure_reason": row["failure_reason"],
                "actual": row["actual_behavior"],
            }
        elif not row["pass"]:
            assert row["failure_class"] in {"A", "B", "C", "D"}
            assert row["failure_reason"]


def test_adversarial_reported_failures_are_not_silently_green():
    """Report-only items may fail; the suite still collects them as explicit fails."""
    report = run_adversarial()
    reported = [r for r in report["items"] if not r["must_pass"]]
    assert reported
    for row in reported:
        if not row["pass"]:
            assert row["failure_class_label"]
