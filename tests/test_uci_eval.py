from __future__ import annotations

import json
from pathlib import Path

from analysis.eval.uci_retail import run_uci_retail

ROOT = Path(__file__).resolve().parents[1]


def test_uci_retail_rubric_has_ten_process_cases():
    catalog = json.loads((ROOT / "evals" / "uci_retail.json").read_text(encoding="utf-8"))
    assert len(catalog["items"]) >= 10
    report = run_uci_retail()
    assert report["skipped"] is False
    failed = [r for r in report["items"] if not r["pass"]]
    assert report["pass"], failed
    assert report["n_scored"] >= 10
