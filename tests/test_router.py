from __future__ import annotations

from analysis.router import route_turn

CAPS = {
    "temporal_analysis": True,
    "metric_comparison": True,
    "segmentation": True,
    "volume_value_decomposition": True,
    "retention_analysis": False,
    "delivery_analysis": False,
    "causal_analysis": False,
    "multi_table_join": False,
}


def test_first_why_change_investigates():
    d = route_turn("Satışlar neden düştü?", has_run=False, capabilities=CAPS)
    assert d.intent == "investigate"


def test_west_followup_uses_existing_evidence():
    run = {"primary_driver": "West × Office Supplies", "evidence": []}
    d = route_turn(
        "Peki West'te durum nasıl?",
        has_run=True,
        last_run=run,
        capabilities=CAPS,
    )
    assert d.intent == "answer_from_evidence"
    assert "West" in d.focus_labels


def test_west_why_starts_scoped_investigation():
    run = {"primary_driver": "West × Office Supplies", "evidence": []}
    d = route_turn(
        "Peki West'te neden?",
        has_run=True,
        last_run=run,
        capabilities=CAPS,
    )
    assert d.intent == "follow_up_investigate"
    assert "West" in d.focus_labels


def test_detail_drill_is_scoped_investigation():
    run = {"primary_driver": "West × Office Supplies", "evidence": []}
    d = route_turn(
        "West'i daha detaylı incele.",
        has_run=True,
        last_run=run,
        capabilities=CAPS,
    )
    assert d.intent == "follow_up_investigate"


def test_worst_category_does_not_reinvestigate():
    d = route_turn("En kötü kategori hangisi?", has_run=True, last_run={"evidence": []}, capabilities=CAPS)
    assert d.intent == "answer_from_evidence"
    assert d.reason == "ranking"


def test_causal_probe_does_not_reinvestigate():
    d = route_turn("Bunun nedeni ne?", has_run=True, last_run={"decision": "primary_driver"}, capabilities=CAPS)
    assert d.intent == "answer_from_evidence"
    assert d.reason == "causal_probe"


def test_churn_abstains_without_capability():
    d = route_turn(
        "Bu veriyle müşteri kaybını analiz edebilir miyiz?",
        has_run=False,
        capabilities=CAPS,
    )
    assert d.intent == "abstain_capability"
    assert d.missing_capability == "retention_analysis"


def test_sql_is_still_not_executed_as_sql():
    d = route_turn("SELECT * FROM orders; --", has_run=False, capabilities=CAPS)
    assert d.intent == "investigate"


def test_meta_intents_still_work():
    run = {"id": "run-1"}
    assert route_turn("Araştırma adımlarını göster.", has_run=True, last_run=run).intent == "show_steps"
    assert route_turn("Detaylı raporu göster.", has_run=True, last_run=run).intent == "show_report"
    assert route_turn("Evidence listesini göster.", has_run=True, last_run=run).intent == "show_evidence"
