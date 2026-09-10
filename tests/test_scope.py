from __future__ import annotations

import pandas as pd

from analysis.graph import run_investigation
from analysis.scope import apply_scope, resolve_scope, scope_lead
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def test_resolve_scope_maps_region_from_segment_rows():
    run = {
        "evidence": [
            {
                "operation": "segment_by",
                "filters": {"dimensions": ["region", "category"]},
                "value": {
                    "rows": [
                        {"region": "West", "category": "Office Supplies", "change": -80.0},
                        {"region": "East", "category": "Furniture", "change": -5.0},
                    ]
                },
            }
        ]
    }
    assert resolve_scope(run, ["West"]) == {"region": "West"}
    assert resolve_scope(run, ["West", "Office Supplies"]) == {
        "region": "West",
        "category": "Office Supplies",
    }


def test_apply_scope_filters_rows():
    df = pd.DataFrame({"region": ["West", "East", "West"], "sales": [1, 2, 3]})
    out = apply_scope(df, {"region": "West"})
    assert list(out["region"]) == ["West", "West"]


def test_scope_lead_mentions_slice():
    assert "West" in scope_lead({"region": "West"})
    assert "hipotez" in scope_lead({"region": "West"})


def test_graph_scope_does_not_use_other_regions():
    scoped = run_investigation(
        FIXTURES / "clear_driver.csv",
        "Satış neden değişti?",
        scope={"region": "West"},
    )
    assert scoped["scope"] == {"region": "West"}
    assert scoped.get("error") is None
    for ev in scoped["evidence"]:
        if ev.get("operation") != "segment_by":
            continue
        for row in (ev.get("value") or {}).get("rows") or []:
            if "region" in row:
                assert row["region"] == "West"
