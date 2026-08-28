from __future__ import annotations

from pathlib import Path

from analysis.evidence.models import Claim, Evidence
from analysis.graph import run_investigation
from analysis.reviewer import publish_claims, review_claims
from analysis.tools.schemas import V1_TOOLS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def _ev(eid: str, value: dict, strength: str = "strong") -> Evidence:
    return Evidence(
        evidence_id=eid,
        operation="compare_periods",
        source_columns=["sales"],
        value=value,
        strength=strength,  # type: ignore[arg-type]
    )


def test_reviewer_is_not_a_tool():
    assert "review_claims" not in V1_TOOLS


def test_valid_number_accept():
    ev = _ev("e1", {"change_pct": -30.0})
    claim = Claim(
        claim_id="c1",
        text="Sales declined by -30%.",
        kind="association",
        evidence_ids=["e1"],
        provenance_ok=True,
    )
    v = review_claims([claim], [ev], "association")[0]
    assert v.decision == "accept"


def test_unsupported_number_reject():
    ev = _ev("e1", {"change_pct": -30.0})
    claim = Claim(
        claim_id="c1",
        text="Sales declined by 42%.",
        kind="association",
        evidence_ids=["e1"],
    )
    v = review_claims([claim], [ev], "association")[0]
    assert v.decision == "reject"
    assert "unbound_number" in v.issues


def test_causal_reject():
    ev = _ev("e1", {"r": -0.4})
    claim = Claim(
        claim_id="c1",
        text="Discount caused profit decline.",
        kind="association",
        evidence_ids=["e1"],
    )
    v = review_claims([claim], [ev], "association")[0]
    assert v.decision == "reject"
    assert "causal_language" in v.issues


def test_missing_evidence_reject():
    claim = Claim(
        claim_id="c1",
        text="Region A caused the decline.",
        kind="association",
        evidence_ids=[],
    )
    v = review_claims([claim], [], "abstain")[0]
    assert v.decision == "reject"


def test_correct_abstention_accept():
    claim = Claim(
        claim_id="c1",
        text="No concentrated association is supported; insufficient evidence.",
        kind="abstention",
        evidence_ids=[],
        provenance_ok=True,
    )
    v = review_claims([claim], [], "abstain", "abstain")[0]
    assert v.decision == "accept"


def test_overclaim_weak_evidence_reject():
    ev = _ev("e1", {"share_of_change": 0.1}, strength="weak")
    claim = Claim(
        claim_id="c1",
        text="Region A is the primary driver.",
        kind="association",
        evidence_ids=["e1"],
        provenance_ok=True,
    )
    v = review_claims([claim], [ev], "abstain")[0]
    assert v.decision == "reject"
    assert "overclaim" in v.issues or "strength_mismatch" in v.issues


def test_association_language_accept():
    ev = _ev("e1", {"r": -0.2, "n": 100}, strength="weak")
    claim = Claim(
        claim_id="c1",
        text="Delay is associated with review score (r=-0.2, n=100).",
        kind="association",
        evidence_ids=["e1"],
        provenance_ok=True,
    )
    v = review_claims([claim], [ev], "association")[0]
    assert v.decision == "accept"


def test_unknown_evidence_id_reject():
    claim = Claim(
        claim_id="c1",
        text="Sales declined by 30%.",
        kind="association",
        evidence_ids=["missing"],
    )
    v = review_claims([claim], [_ev("e1", {"change_pct": -30.0})], "association")[0]
    assert v.decision == "reject"
    assert "unknown_evidence_id" in v.issues


def test_fake_confidence_reject():
    ev = _ev("e1", {"change_pct": -30.0})
    claim = Claim(
        claim_id="c1",
        text="Sales declined by -30% with 89% confidence.",
        kind="association",
        evidence_ids=["e1"],
    )
    v = review_claims([claim], [ev], "association")[0]
    assert v.decision == "reject"
    assert "fake_confidence" in v.issues


def test_budget_partial_vs_unbound():
    ev = _ev("e1", {"change_pct": -18.0})
    ok = Claim(
        claim_id="c1",
        text="Sales declined by -18%.",
        kind="association",
        evidence_ids=["e1"],
        provenance_ok=True,
    )
    bad = Claim(
        claim_id="c2",
        text="West is the primary driver.",
        kind="association",
        evidence_ids=[],
        provenance_ok=True,
    )
    v_ok, v_bad = review_claims([ok, bad], [ev], "abstain", "budget")
    assert v_ok.decision == "accept"
    assert v_bad.decision == "reject"


def test_revise_drove_wording():
    ev = _ev("e1", {"change_pct": -18.0}, strength="moderate")
    claim = Claim(
        claim_id="c1",
        text="West drove the sales change of -18%.",
        kind="association",
        evidence_ids=["e1"],
        provenance_ok=True,
    )
    v = review_claims([claim], [ev], "association")[0]
    assert v.decision == "revise"
    published = publish_claims([claim], [v])
    assert published
    assert "drove" not in published[0].text.lower()


def test_v1_clear_driver_still_accepted():
    out = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    assert out["decision"] == "primary_driver"
    assert "review_claims" in out["plan"]
    assert out["reviews"]
    assert out["reviews"][0]["decision"] == "accept"
    assert out["claims"]
    assert out["claims"][0]["kind"] == "association"
