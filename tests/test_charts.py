from __future__ import annotations

from pathlib import Path

from analysis.charts import build_charts
from analysis.graph import run_investigation

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _run(
    question: str,
    decision: str,
    evidence: list[dict],
    claims: list[dict] | None = None,
) -> dict:
    return {
        "question": question,
        "decision": decision,
        "claims": claims or [],
        "reviews": [],
        "evidence": evidence,
    }


def test_trend_is_line_from_period_totals():
    charts = build_charts(
        _run(
            "Satış neden değişti?",
            "primary_driver",
            [
                {
                    "evidence_id": "e-cmp",
                    "operation": "compare_periods",
                    "value": {"previous": 100.0, "current": 80.0, "metric": "sales"},
                    "period": {
                        "previous": {"end": "2016-12"},
                        "current": {"end": "2017-12"},
                    },
                }
            ],
        )
    )
    assert len(charts) == 1
    assert charts[0]["kind"] == "line"
    assert charts[0]["purpose"] == "trend"
    ys = (charts[0]["plotly"]["data"][0]["y"])
    assert list(ys) == [100.0, 80.0]


def test_ranking_uses_segment_bar_not_waterfall():
    rows = [
        {"region": "West", "change": -40.0, "share_of_change": 0.8},
        {"region": "East", "change": -10.0, "share_of_change": 0.2},
    ]
    charts = build_charts(
        _run(
            "Hangi bölge en yüksek?",
            "ranking",
            [
                {
                    "evidence_id": "e-seg",
                    "operation": "segment_by",
                    "filters": {"dimensions": ["region"]},
                    "value": {"rows": rows},
                },
                {
                    "evidence_id": "e-cmp",
                    "operation": "compare_periods",
                    "value": {"previous": 100.0, "current": 80.0, "metric": "sales"},
                },
            ],
        )
    )
    assert [c["kind"] for c in charts] == ["bar"]
    assert charts[0]["purpose"] == "segment_comparison"


def test_contribution_waterfall_uses_segment_change():
    rows = [
        {"region": "West", "category": "Furniture", "change": -30.0, "share_of_change": 0.6},
        {"region": "East", "category": "Office", "change": -20.0, "share_of_change": 0.4},
    ]
    charts = build_charts(
        _run(
            "Satış neden değişti?",
            "primary_driver",
            [
                {
                    "evidence_id": "e-2d",
                    "operation": "segment_by",
                    "filters": {"dimensions": ["region", "category"]},
                    "value": {"rows": rows},
                }
            ],
            claims=[{"claim_id": "cl-1", "evidence_ids": ["e-2d"]}],
        )
    )
    assert charts[0]["kind"] == "waterfall"
    assert charts[0]["purpose"] == "contribution"
    assert charts[0]["claim_ids"] == ["cl-1"]
    ys = list(charts[0]["plotly"]["data"][0]["y"])
    assert sorted(ys) == [-30.0, -20.0]


def test_volume_aov_is_two_metric_bar():
    charts = build_charts(
        _run(
            "Satış neden değişti?",
            "value_not_volume",
            [
                {
                    "evidence_id": "e-vol",
                    "operation": "decompose_volume_value",
                    "value": {"volume_change_pct": -12.5, "aov_change_pct": 3.0},
                }
            ],
        )
    )
    assert charts[0]["kind"] == "bar"
    assert charts[0]["purpose"] == "metric_comparison"
    assert list(charts[0]["plotly"]["data"][0]["y"]) == [-12.5, 3.0]


def test_rejected_claims_are_not_bound():
    charts = build_charts(
        {
            "question": "Satış neden değişti?",
            "decision": "primary_driver",
            "claims": [{"claim_id": "cl-bad", "evidence_ids": ["e-cmp"]}],
            "reviews": [{"claim_id": "cl-bad", "decision": "reject"}],
            "evidence": [
                {
                    "evidence_id": "e-cmp",
                    "operation": "compare_periods",
                    "value": {"previous": 1, "current": 2, "metric": "sales"},
                }
            ],
        }
    )
    assert charts[0]["claim_ids"] == []


def test_live_why_change_selects_line_and_waterfall():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    kinds = {c["kind"] for c in run["investigation_report"]["visualizations"]}
    purposes = {c["purpose"] for c in run["investigation_report"]["visualizations"]}
    assert "line" in kinds
    assert "waterfall" in kinds
    assert "trend" in purposes
    assert "contribution" in purposes


def test_live_ranking_is_a_single_bar():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Hangi bölge en yüksek?")
    viz = run["investigation_report"]["visualizations"]
    assert viz
    assert {c["kind"] for c in viz} == {"bar"}
    assert {c["purpose"] for c in viz} == {"segment_comparison"}
