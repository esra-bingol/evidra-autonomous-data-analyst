from __future__ import annotations

from pathlib import Path

from analysis.graph import run_investigation
from analysis.response import ResponseContract, compose_followup, compose_response, validate_response
from analysis.router import CAUSAL_LIMIT

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
    phrase = "Tek bir bölge veya kategoride toplanmış bir değişim görünmüyor."
    assert contract.answer.count(phrase) <= 1
    assert "işaretlenmedi" in contract.answer or "yayıl" in contract.answer
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


def test_followup_causal_probe_uses_limit_sentence():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    contract = compose_followup(run, "Bunun nedeni ne?")
    assert contract.answer.endswith(CAUSAL_LIMIT)
    assert "West" in contract.answer
    ok, reasons = validate_response(contract, run)
    assert ok, reasons


def test_followup_ranking_and_slice_stay_grounded():
    run = run_investigation(FIXTURES / "clear_driver.csv", "Satış neden değişti?")
    worst = compose_followup(run, "En kötü kategori hangisi?")
    assert "associated" not in worst.answer.lower()
    assert "segment_by" not in worst.answer
    assert "office" in worst.answer.lower() or "kategori" in worst.answer.lower()
    ok, reasons = validate_response(worst, run)
    assert ok, reasons
    west = compose_followup(run, "Peki West'te durum nasıl?")
    assert "west" in west.answer.lower()
    assert "segment_by" not in west.answer
    ok, reasons = validate_response(west, run)
    assert ok, reasons


def test_abstain_volume_followup_is_not_the_same_essay():
    run = {
        "decision": "abstain",
        "question": "Satış neden değişti?",
        "claims": [],
        "reviews": [],
        "evidence": [
            {
                "evidence_id": "ev-cmp",
                "operation": "compare_periods",
                "value": {"change_pct": -29.23, "previous": 118448.0, "current": 83829.0},
            },
            {
                "evidence_id": "ev-vol",
                "operation": "decompose_volume_value",
                "value": {"volume_change_pct": -14.18, "aov_change_pct": -17.54},
            },
            {
                "evidence_id": "ev-seg",
                "operation": "segment_by",
                "filters": {"dimensions": ["region"]},
                "value": {
                    "rows": [
                        {
                            "region": "West",
                            "previous": 50000.0,
                            "current": 20000.0,
                            "change": -30000.0,
                            "share_of_change": 0.42,
                        },
                        {
                            "region": "East",
                            "previous": 40000.0,
                            "current": 30000.0,
                            "change": -10000.0,
                            "share_of_change": 0.14,
                        },
                    ]
                },
            },
        ],
    }
    first = compose_response(run)
    follow = compose_followup(run, "Sipariş sayısındaki düşüş hangi dilimde toplanıyor?")
    assert follow.answer != first.answer
    assert "dağılmış" in first.answer or "işaretlenmedi" in first.answer
    assert "west" in follow.answer.lower()
    assert "en büyük pay" in follow.answer.lower()
    assert "dağılmış" not in follow.answer
    assert "en yüksek dilim" not in follow.answer.lower()
    ok, reasons = validate_response(follow, run)
    assert ok, reasons
    assert "sipariş sayısı" in follow.answer.lower()
    assert "adet kırılımı" in follow.answer.lower()


def test_no_signal_ranking_followup_is_not_the_why_essay():
    run = run_investigation(FIXTURES / "no_signal.csv", "Satış neden değişti?")
    first = compose_response(run)
    follow = compose_followup(run, "Sipariş sayısındaki düşüş hangi dilimde toplanıyor?")
    assert follow.answer != first.answer
    assert "dağılmış" not in follow.answer
    low = follow.answer.lower()
    assert "sıralaması mevcut kanıtta yok" in low or "adet olarak hesaplanmadı" in low
    ok, reasons = validate_response(follow, run)
    assert ok, reasons


def test_limitation_survives_from_report():
    run = run_investigation(FIXTURES / "no_signal.csv", "Satış neden değişti?")
    assert run["investigation_report"]["limitations"]
    contract = compose_response(run)
    assert contract.limitations
    assert any("yoğunlaş" in n or "toplan" in n or "desteklenmiyor" in n for n in contract.limitations)


def test_taxi_compose_says_fare_not_sales():
    run = run_investigation(FIXTURES / "taxi_trips.csv", "Ücret neden değişti?")
    contract = compose_response(run)
    assert "Satışlar" not in contract.answer
    assert "West" not in contract.answer
    assert "Ücretler" in contract.answer or "ücret" in contract.answer.lower()
    assert "sürücü" not in contract.answer.lower()
    phrase = "Tek bir bölge veya kategoride toplanmış bir değişim görünmüyor."
    assert contract.answer.count(phrase) <= 1
    ok, reasons = validate_response(contract, run)
    assert ok, reasons
