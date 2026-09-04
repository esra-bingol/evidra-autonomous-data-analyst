from __future__ import annotations

from pathlib import Path

from analysis.graph import run_investigation
from analysis.report import SECTION_KEYS, build_investigation_report
from analysis.tools.schemas import V1_TOOLS

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _flatten_numbers(obj) -> list[float]:
    out: list[float] = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_flatten_numbers(v))
        return out
    if isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_flatten_numbers(v))
    return out


def test_report_uses_published_claims_only():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    report = run["investigation_report"]
    assert set(SECTION_KEYS) <= set(report)
    assert report["source"] == "validated_investigation_state"
    claim_ids = [c["claim_id"] for c in run["claims"]]
    finding_ids = [f["claim_id"] for f in report["key_findings"]]
    assert finding_ids == claim_ids
    assert report["investigation_question"] == "Satış neden değişti?"
    assert report["reviewer_decisions"] == run["reviews"]


def test_charts_bind_evidence_and_are_not_a_fixed_count():
    driver = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    report = driver["investigation_report"]
    viz = report["visualizations"]
    assert viz, "clear_driver should produce purposeful charts from evidence"
    assert len(viz) < 10
    evid_ids = {e["evidence_id"] for e in driver["evidence"]}
    pool = _flatten_numbers([e.get("value") for e in driver["evidence"]])
    for ch in viz:
        assert ch["evidence_ids"]
        assert set(ch["evidence_ids"]) <= evid_ids
        assert ch["purpose"]
        ys = []
        for trace in (ch.get("plotly") or {}).get("data") or []:
            ys.extend(_flatten_numbers(trace.get("y")))
        for y in ys:
            assert any(abs(y - n) < 1e-6 for n in pool), y
    abstain = run_investigation(FIXTURES / "clear_driver.csv", "Teslimat gecikmesi puanı nasıl etkiler?")
    assert abstain["decision"] == "abstain"
    other = abstain["investigation_report"]["visualizations"]
    assert len(other) != len(viz)


def test_report_does_not_add_tools_or_python():
    assert "run_python" not in V1_TOOLS
    report = build_investigation_report(
        {
            "question": "q",
            "decision": "abstain",
            "claims": [{"claim_id": "cl-001", "text": "No concentrated association.", "kind": "abstention", "evidence_ids": []}],
            "reviews": [{"claim_id": "cl-001", "decision": "accept", "reason": "ok"}],
            "evidence": [],
            "plan": ["inspect_dataset"],
            "hypotheses": [],
            "traces": [],
            "research_steps": [],
        }
    )
    assert report["visualizations"] == []
    assert report["key_findings"][0]["claim_id"] == "cl-001"
    assert report["key_findings"][0]["chart_ids"] == []
