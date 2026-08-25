from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis.evidence import (
    Chart,
    Claim,
    EvidenceLog,
    lock_investigation,
    validate_claim,
)
from analysis.load import load_tabular
from analysis.periods import compare_periods

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def _log_with_compare() -> tuple[EvidenceLog, str]:
    df = load_tabular(FIXTURES / "clear_driver.csv")
    log = EvidenceLog()
    ev = log.append_result(compare_periods(df))
    return log, ev.evidence_id


def test_no_evidence_no_claim():
    log, _eid = _log_with_compare()
    claim = Claim(
        claim_id="bad",
        text="Sales changed.",
        kind="association",
        evidence_ids=[],
    )
    out = validate_claim(claim, log)
    assert out.provenance_ok is False


def test_unknown_evidence_id_rejected():
    log, eid = _log_with_compare()
    claim = Claim(
        claim_id="bad",
        text="Sales changed.",
        kind="association",
        evidence_ids=["ev-does-not-exist"],
    )
    assert validate_claim(claim, log).provenance_ok is False
    ok = Claim(
        claim_id="ok",
        text="Sales changed.",
        kind="association",
        evidence_ids=[eid],
    )
    assert validate_claim(ok, log).provenance_ok is True


def test_causal_verb_rejected():
    log, eid = _log_with_compare()
    for text in (
        "West caused the sales drop.",
        "Sales fell because of West.",
        "Root cause is Office Supplies.",
        "Düşüşün sebebi West.",
        "West neden oldu.",
    ):
        claim = Claim(claim_id="c", text=text, kind="association", evidence_ids=[eid])
        assert validate_claim(claim, log).provenance_ok is False, text


def test_unbound_number_rejected():
    log, eid = _log_with_compare()
    claim = Claim(
        claim_id="c",
        text="Sales fell 99.0%.",
        kind="association",
        evidence_ids=[eid],
    )
    assert validate_claim(claim, log).provenance_ok is False


def test_fake_confidence_rejected():
    log, eid = _log_with_compare()
    claim = Claim(
        claim_id="c",
        text="We have 89% confidence in this association.",
        kind="association",
        evidence_ids=[eid],
    )
    assert validate_claim(claim, log).provenance_ok is False


def test_compare_periods_claim_can_be_provenance_ok():
    locked = lock_investigation(str(FIXTURES / "clear_driver.csv"))
    assert locked["decision"] == "primary_driver"
    assert locked["claims"]
    assert all(c["provenance_ok"] for c in locked["claims"])
    assert locked["claims"][0]["kind"] == "association"
    assert locked["claims"][0]["evidence_ids"]


def test_chart_requires_evidence_ids():
    with pytest.raises(ValidationError):
        Chart(kind="trend", plotly={"data": []}, evidence_ids=[])
    locked = lock_investigation(str(FIXTURES / "clear_driver.csv"))
    assert locked["charts"]
    for chart in locked["charts"]:
        assert chart["evidence_ids"]


def test_evidence_log_is_append_only():
    log, eid = _log_with_compare()
    with pytest.raises((ValueError, TypeError)):
        log.append_result(log.get(eid).model_dump(), evidence_id=eid)
    with pytest.raises(TypeError):
        log.replace(eid, strength="weak")
    ev = log.get(eid)
    with pytest.raises(Exception):
        ev.strength = "weak"  # type: ignore[misc]
    assert log.get(eid).strength == ev.strength


def test_no_signal_claim_is_abstention():
    locked = lock_investigation(str(FIXTURES / "no_signal.csv"))
    kinds = {c["kind"] for c in locked["claims"]}
    assert kinds <= {"abstention"}
    assert locked["decision"] == "abstain"
    text = locked["claims"][0]["text"].lower()
    assert "inconclusive" in text or "capability" in text
    assert locked["claims"][0]["provenance_ok"] is True
    assert locked["claims"][0]["evidence_ids"] == []


def test_abstention_may_have_empty_evidence_ids():
    log = EvidenceLog()
    claim = Claim(
        claim_id="abs",
        text="Inconclusive; no capability supports a driver claim.",
        kind="abstention",
        evidence_ids=[],
    )
    assert validate_claim(claim, log).provenance_ok is True


def test_number_lock_uses_tolerance():
    log, eid = _log_with_compare()
    ev = log.get(eid)
    pct = float(ev.value["change_pct"])
    near = Claim(
        claim_id="near",
        text=f"Sales change is {pct}%.",
        kind="association",
        evidence_ids=[eid],
    )
    assert validate_claim(near, log).provenance_ok is True
    far = Claim(
        claim_id="far",
        text="Sales change is 99.0%.",
        kind="association",
        evidence_ids=[eid],
    )
    assert validate_claim(far, log).provenance_ok is False
