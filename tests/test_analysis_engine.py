from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis.capabilities import detect_capabilities
from analysis.investigate import investigate
from analysis.load import load_tabular
from analysis.periods import compare_periods
from analysis.profiler import profile_dataset
from analysis.roles import infer_roles
from analysis.segments import segment_by
from analysis.statistics import association_test
from analysis.visualization import create_visualization

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"
SUPERSTORE = ROOT / "data" / "raw" / "superstore.csv"


def _expected(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.expected.json").read_text(encoding="utf-8"))


def test_clear_driver_primary_driver():
    result = investigate(FIXTURES / "clear_driver.csv")
    exp = _expected("clear_driver")
    assert result["primary_driver"] == exp["primary_driver"]
    assert result["decision"] == "primary_driver"
    pct = result["compare_periods"]["value"]["change_pct"]
    lo, hi = exp["sales_change_pct_band"]
    assert lo <= pct <= hi
    for key in ("operation", "source_columns", "filters", "period", "value"):
        assert key in result["compare_periods"]


def test_clear_driver_interaction_ranks_west_office():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    seg = segment_by(df, ["region", "category"])
    top = seg.value["rows"][0]
    assert top["region"] == "West"
    assert top["category"] == "Office Supplies"
    assert top["share_of_change"] >= 0.9


def test_aov_trap_is_value_not_volume():
    result = investigate(FIXTURES / "aov_trap.csv")
    assert result["decision"] == "value_not_volume"
    assert result["primary_driver"] == "AOV"
    vol = result["volume_value"]["value"]
    assert abs(vol["volume_change_pct"]) <= 10
    assert abs(vol["aov_change_pct"]) >= 20


def test_no_signal_does_not_name_a_segment_driver():
    result = investigate(FIXTURES / "no_signal.csv")
    assert result["decision"] == "abstain"
    assert result["primary_driver"] is None


def test_missingness_is_artefact():
    result = investigate(FIXTURES / "missingness.csv")
    assert result["decision"] == "data_artefact"
    assert result["primary_driver"] is None
    assert result["coverage"]["value"]["truncated_current_period"] is True


def test_delivery_capability_false_on_fixtures():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    roles = infer_roles(df)
    caps = detect_capabilities(roles).value
    assert caps["delivery_analysis"] is False
    assert caps["causal_analysis"] is False
    assert caps["multi_table_join"] is False


def test_two_charts():
    df = load_tabular(FIXTURES / "clear_driver.csv")
    trend = create_visualization(df, kind="trend")
    bar = create_visualization(df, kind="segment")
    assert "plotly" in trend.value
    assert "plotly" in bar.value
    assert trend.operation == "create_visualization"


def test_association_is_not_causal():
    df = load_tabular(FIXTURES / "aov_trap.csv")
    out = association_test(df, "sales", "quantity")
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
