from __future__ import annotations

from pathlib import Path

from analysis.graph import run_investigation
from analysis.response import ResponseContract, compose_response, validate_response

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def test_clear_driver_natural_turkish_grounded():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    contract = compose_response(run)
    text = contract.answer.lower()
    assert "associated" not in text
    assert "primary_driver" not in text
    assert "share_of_change" not in text
    assert "neden oldu" not in text
    assert "sebep" not in text
    assert "west" in text
    assert "office supplies" in text
    assert "%" in contract.answer
    assert contract.evidence_refs
    evid = {e["evidence_id"] for e in run["evidence"]}
    assert set(contract.evidence_refs) <= evid
    ok, reasons = validate_response(contract, run)
    assert ok, reasons
    assert contract.limitations
    assert any("nedeni kesin" in n or "ilişki" in n for n in contract.limitations)


def test_aov_trap_preserves_value_not_volume():
    run = run_investigation(FIXTURES / "aov_trap.csv", "Satış neden değişti?")
    contract = compose_response(run)
    text = contract.answer.lower()
    assert "associated" not in text
    assert "neden oldu" not in text
    assert "aov" in text or "sepet" in text
    if run["decision"] == "value_not_volume":
        assert "sipariş hacminden çok" in text or "aov" in text
        assert "hacmindeki daralma" not in text
    ok, reasons = validate_response(contract, run)
    assert ok, reasons


def test_no_signal_does_not_invent_driver():
    run = run_investigation(FIXTURES / "no_signal.csv", "Satış neden değişti?")
    contract = compose_response(run)
    assert run["decision"] == "abstain"
    assert "en güçlü desteklenen sinyal" not in contract.answer
    assert "west" not in contract.answer.lower()
    assert contract.limitations
    ok, reasons = validate_response(contract, run)
    assert ok, reasons


def test_rejected_claims_are_not_key_findings():
    run = {
        "decision": "primary_driver",
        "primary_driver": "West × Furniture",
        "claims": [
            {
                "claim_id": "cl-bad",
                "text": "West is the driver",
                "kind": "association",
                "evidence_ids": ["ev-1"],
            }
        ],
        "reviews": [{"claim_id": "cl-bad", "decision": "reject", "reason": "lock"}],
        "evidence": [
            {
                "evidence_id": "ev-1",
                "operation": "compare_periods",
                "value": {"change_pct": -10.0},
            }
        ],
        "investigation_report": {"limitations": ["The investigation abstained; no unique driver is established."]},
    }
    contract = compose_response(run)
    assert "West × Furniture" not in " ".join(contract.key_findings)
    assert "en güçlü desteklenen sinyal" not in contract.answer


def test_validator_rejects_unbound_number():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    bad = ResponseContract(answer="Satışlar %333,3 düştü.", evidence_refs=[])
    ok, reasons = validate_response(bad, run)
    assert ok is False
    assert "unbound_number" in reasons


def test_validator_rejects_unknown_evidence_ref():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    bad = ResponseContract(answer="Satışlar değişti.", evidence_refs=["ev-does-not-exist"])
    ok, reasons = validate_response(bad, run)
    assert ok is False
    assert "unknown_evidence_id" in reasons


def test_validator_rejects_causal_wording():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    bad = ResponseContract(answer="Satışların düşmesine West neden oldu.")
    ok, reasons = validate_response(bad, run)
    assert ok is False
    assert "causal_language" in reasons


def test_limitation_survives_from_report():
    run = run_investigation(FIXTURES / "no_signal.csv", "Satış neden değişti?")
    assert run["investigation_report"]["limitations"]
    contract = compose_response(run)
    assert contract.limitations
    assert any("sürücü" in n or "desteklenmiyor" in n for n in contract.limitations)
