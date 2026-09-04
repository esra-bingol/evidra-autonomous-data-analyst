from __future__ import annotations

from pathlib import Path

from analysis.graph import run_investigation
from analysis.load import load_source, load_tabular
from analysis.retail import looks_like_retail_line_item
from analysis.roles import infer_roles
from analysis.tools.schemas import V1_TOOLS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "fixtures" / "retail_line_items.csv"
CLEAR = ROOT / "data" / "fixtures" / "clear_driver.csv"


def test_adapter_does_not_add_dataset_tools():
    assert "run_python" not in V1_TOOLS
    assert "calculate_uci_revenue" not in V1_TOOLS
    assert V1_TOOLS[-1] == "generate_report"


def test_uci_schema_canonicalizes_without_hardcoded_sales_column():
    raw = load_tabular(FIXTURE)
    assert looks_like_retail_line_item(raw)
    assert "Sales" not in raw.columns
    src = load_source(FIXTURE)
    assert src.meta["kind"] == "retail_line_item"
    assert "amount" in src.df.columns
    roles = infer_roles(src.df)
    by_name = {r["name"]: r for r in roles}
    assert by_name["amount"]["semantic"] == "sales"
    assert by_name["InvoiceDate"]["role"] == "time"
    assert by_name["Country"]["role"] == "dimension"
    assert by_name["Invoice"]["role"] == "id"
    can = src.meta["assemble"]["value"]
    assert can["derived_in_adapter"] is True
    assert can["dropped_cancelled_or_negative"] >= 1


def test_synthetic_fixture_is_not_retail_schema():
    assert not looks_like_retail_line_item(load_tabular(CLEAR))
    src = load_source(CLEAR)
    assert src.meta["kind"] == "single"


def test_delivery_and_profit_abstain_on_retail_schema():
    delay = run_investigation(FIXTURE, "Teslimat gecikmesi puanı nasıl etkiler?")
    assert delay["decision"] == "abstain"
    assert delay["hypotheses"] == []
    profit = run_investigation(FIXTURE, "What is the profit margin by category?")
    assert profit["decision"] == "abstain"


def test_sales_question_has_period_and_country_evidence():
    out = run_investigation(FIXTURE, "Satış neden değişti?")
    ops = {e["operation"] for e in out["evidence"]}
    assert "canonicalize" in ops
    assert "compare_periods" in ops
    assert "decompose_volume_value" in ops
    assert out["stop_reason"] in {"strong_evidence", "space_exhausted", "budget", "abstain"}
    cmp = next(e for e in out["evidence"] if e["operation"] == "compare_periods")
    assert cmp["value"]["metric"] == "amount"
    by_name = {r["name"]: r for r in out["roles"]}
    assert by_name["Country"]["role"] == "dimension"
    rank = run_investigation(FIXTURE, "Hangi ülke en yüksek?")
    segs = [e for e in rank["evidence"] if e["operation"] == "segment_by"]
    assert any("Country" in ((e.get("filters") or {}).get("dimensions") or []) for e in segs)
    blob = str(out["claims"]).lower()
    assert "cause" not in blob
    assert out["reviews"]
