from __future__ import annotations

from pathlib import Path

import pytest

from analysis.evidence.log import EvidenceLog
from analysis.graph import run_investigation
from analysis.heuristic import run_heuristic
from analysis.load import load_source
from analysis.olist import olist_available
from analysis.tools.runtime import ToolContext, call_tool

ROOT = Path(__file__).resolve().parents[1]
OLIST = ROOT / "data" / "raw"
SUPERSTORE = OLIST / "superstore.csv"

pytestmark = pytest.mark.skipif(not olist_available(OLIST), reason="Olist CSVs not local")


def test_olist_capabilities_and_superstore_still_abstains():
    src = load_source(OLIST)
    assert src.meta["n_tables"] >= 2
    caps = run_investigation(OLIST, "Teslimat gecikmesi ile review score arasında association var mı?")
    assert caps["capabilities"]["multi_table_join"] is True
    assert caps["capabilities"]["delivery_analysis"] is True
    assert caps["capabilities"]["retention_analysis"] is True
    assert caps["capabilities"]["causal_analysis"] is False
    if SUPERSTORE.exists():
        ss = run_heuristic(SUPERSTORE, "What is the effect of delivery delay on satisfaction?")
        assert ss["hypotheses"] == []
        assert ss["capabilities"].get("delivery_analysis") is False


def test_olist_delay_review_join_case():
    out = run_investigation(
        OLIST, "Teslimat gecikmesi ile review score arasında association var mı?"
    )
    join = next(e for e in out["evidence"] if e["operation"] == "join_assemble")
    assert len(join["value"]["tables"]) >= 2
    assert join["value"]["delay_column"] == "delay_days"
    assert {"order_id", "customer_id", "product_id"} <= set(join["value"]["join_keys"])
    assert out["decision"] == "association"
    blob = str(out["claims"]).lower()
    assert "cause" not in blob
    assert "because" not in blob
    assoc = next(e for e in out["evidence"] if e["operation"] == "association_test")
    assert "review_score" in assoc["source_columns"]
    assert "delay_days" in assoc["source_columns"]


def test_olist_category_gmv_join_case_and_sql():
    out = run_investigation(OLIST, "Yüksek ciro, düşük puan kategorileri hangileri?")
    ops = {e["operation"] for e in out["evidence"]}
    assert "join_assemble" in ops
    assert "run_sql" in ops
    sql = next(e for e in out["evidence"] if e["operation"] == "run_sql")
    assert sql["value"]["n"] >= 1
    assert out["hypotheses"]
    assert all(h["template_id"] == "association" for h in out["hypotheses"])


def test_olist_profit_question_abstains():
    out = run_investigation(OLIST, "What is the profit margin by category?")
    assert out["decision"] == "abstain"
    assert out["hypotheses"] == []


def test_olist_join_sql_on_catalog_tables():
    src = load_source(OLIST)
    ctx = ToolContext(df=src.df, log=EvidenceLog(), tables=src.tables, catalog_meta=src.meta)
    ok = call_tool(
        ctx,
        "run_sql",
        sql="SELECT o.order_id FROM orders o JOIN reviews r ON o.order_id = r.order_id LIMIT 5",
    )
    assert ok.ok
