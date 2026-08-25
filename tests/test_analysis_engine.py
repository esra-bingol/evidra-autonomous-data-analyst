from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from analysis.anomalies import detect_anomalies
from analysis.capabilities import detect_capabilities
from analysis.investigate import investigate
from analysis.load import load_tabular
from analysis.periods import compare_periods, current_coverage
from analysis.profiler import profile_dataset
from analysis.quality import detect_duplicates, detect_missing_values, quality_score
from analysis.roles import infer_roles
from analysis.segments import segment_by
from analysis.statistics import association_test, summary_statistics
from analysis.visualization import create_visualization
from analysis.volume_value import decompose_volume_value

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"
SUPERSTORE = ROOT / "data" / "raw" / "superstore.csv"
PROVENANCE = ("operation", "source_columns", "filters", "period", "value")
CAUSAL_TOKENS = ("cause", "because", "root cause", "sebep", "neden oldu")


def _expected(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.expected.json").read_text(encoding="utf-8"))


def test_clear_driver_matches_expected_bindings():
    exp = _expected("clear_driver")
    result = investigate(FIXTURES / "clear_driver.csv")
    assert result["primary_driver"] == exp["primary_driver"]
    assert result["decision"] == "primary_driver"
    pct = result["compare_periods"]["value"]["change_pct"]
    lo, hi = exp["sales_change_pct_band"]
    assert lo <= pct <= hi


def test_clear_driver_interaction_uses_expected_cell():
    exp = _expected("clear_driver")
    df = load_tabular(FIXTURES / "clear_driver.csv")
    seg = segment_by(df, ["region", "category"])
    top = seg.value["rows"][0]
    assert top["region"] == exp["driver_region"]
    assert top["category"] == exp["driver_category"]
    assert top["share_of_change"] >= 0.9


def test_engine_does_not_hardcode_driver_labels():
    src = (ROOT / "analysis").read_text() if False else ""
    _ = src
    engine_dir = ROOT / "analysis"
    blob = "\n".join(p.read_text(encoding="utf-8") for p in engine_dir.glob("*.py"))
    assert "West × Office Supplies" not in blob
    assert "Office Supplies" not in blob


def test_aov_trap_does_not_select_volume():
    exp = _expected("aov_trap")
    result = investigate(FIXTURES / "aov_trap.csv")
    assert result["decision"] == exp["decision"]
    assert result["primary_driver"] == "AOV"
    vol = result["volume_value"]["value"]
    assert abs(vol["volume_change_pct"]) <= 10
    assert abs(vol["aov_change_pct"]) >= 20
    assert abs(vol["aov_change_pct"]) > abs(vol["volume_change_pct"])


def test_no_signal_abstains_even_if_a_cell_ranks_first():
    result = investigate(FIXTURES / "no_signal.csv")
    assert result["decision"] == "abstain"
    assert result["primary_driver"] is None
    rows = result["interaction"]["value"]["rows"]
    assert rows, "ranking may exist; it must not become the answer"
    slim = json.dumps(
        {"decision": result["decision"], "primary_driver": result["primary_driver"]},
        ensure_ascii=False,
    )
    top = rows[0]
    worst = f"{top['region']} × {top['category']}"
    assert worst not in slim


def test_missingness_is_artefact():
    result = investigate(FIXTURES / "missingness.csv")
    assert result["decision"] == "data_artefact"
    assert result["primary_driver"] is None
    assert result["coverage"]["value"]["truncated_current_period"] is True


def test_quality_score_is_not_claim_confidence():
    quiet = investigate(FIXTURES / "no_signal.csv")
    assert quiet["quality"]["value"]["kind"] == "data_quality"
    assert quiet["quality"]["value"]["not"] == "claim_confidence"
    assert quiet["quality"]["value"]["score"] >= 90
    assert quiet["decision"] == "abstain"


def test_investigate_output_has_no_causal_language():
    for name in ("clear_driver", "aov_trap", "no_signal", "missingness"):
        clipped = {k: v for k, v in investigate(FIXTURES / f"{name}.csv").items() if k != "charts"}
        payload = json.dumps(clipped, ensure_ascii=False).lower()
        for token in CAUSAL_TOKENS:
            assert re.search(rf"\b{re.escape(token)}\b", payload) is None


def test_engine_results_carry_provenance():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    roles = infer_roles(df)
    results = [
        profile_dataset(df),
        detect_missing_values(df),
        detect_duplicates(df),
        quality_score(df),
        detect_capabilities(roles),
        compare_periods(df),
        current_coverage(df),
        segment_by(df, ["region"]),
        segment_by(df, ["region", "category"]),
        decompose_volume_value(df),
        association_test(df, "sales", "quantity"),
        summary_statistics(df),
        detect_anomalies(df),
        create_visualization(df, kind="trend"),
        create_visualization(df, kind="segment"),
    ]
    for result in results:
        dumped = result.to_dict()
        for key in PROVENANCE:
            assert key in dumped, f"{result.operation} missing {key}"


def test_delivery_capability_false_on_fixtures():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    caps = detect_capabilities(infer_roles(df)).value
    assert caps["delivery_analysis"] is False
    assert caps["causal_analysis"] is False
    assert caps["multi_table_join"] is False


def test_association_is_not_causal():
    out = association_test(load_tabular(FIXTURES / "aov_trap.csv"), "sales", "quantity")
    assert out.value["interpretation"] == "association_only"
    assert "p_value" in out.value


@pytest.mark.skipif(not SUPERSTORE.exists(), reason="superstore.csv is local-only")
def test_superstore_periods_and_region():
    df = load_tabular(SUPERSTORE)
    roles = profile_dataset(df).value["roles"]
    caps = detect_capabilities(roles).value
    assert caps["delivery_analysis"] is False
    cmp = compare_periods(df)
    assert cmp.value["change_pct"] is not None
    region = next(r["name"] for r in roles if r["semantic"] == "region")
    seg = segment_by(df, [region])
    assert len(seg.value["rows"]) >= 2
