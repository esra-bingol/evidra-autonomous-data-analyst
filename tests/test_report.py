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
    assert report["schema_version"] == "v2.11"
    assert report["source"] == "validated_investigation_state"
    rejected = {
        v["claim_id"]
        for v in run["reviews"]
        if v.get("decision") == "reject"
    }
    finding_ids = [f["claim_id"] for f in report["key_findings"]]
    for cid in finding_ids:
        assert cid not in rejected
    assert report["investigation_question"] == "Satış neden değişti?"
    assert report["reviewer_decisions"] == run["reviews"]
    assert "associated" not in report["executive_summary"].lower()
    assert "primary_driver" not in report["executive_summary"]
    assert "west" in report["executive_summary"].lower()
    assert report["title"] == "Satış değişimi incelemesi"
    heads = [h["text"].lower() for h in report["headline_findings"]]
    assert any("west" in h for h in heads)
    assert any("hacim" in h or "sepet" in h for h in heads)
    for h in report["headline_findings"]:
        assert h["n"] >= 1
        evid = {e["evidence_id"] for e in run["evidence"]}
        assert set(h["evidence_ids"]) <= evid
    blob = " ".join(report["limitations"] + report["recommended_next_investigations"] + report["plan_readable"])
    assert "associated" not in blob.lower()
    assert "template" not in blob.lower()
    assert any("ilişki" in n for n in report["limitations"])


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
    assert report["headline_findings"]
    assert "associated" not in report["executive_summary"].lower()
