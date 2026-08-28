from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from analysis.eval.efficiency import overlay_row
from analysis.eval.runner import gate_evidence
from analysis.graph import run_investigation
from analysis.olist import olist_available

ROOT = Path(__file__).resolve().parents[2]
OLIST_ROOT = ROOT / "data" / "raw"
RUBRIC = ROOT / "evals" / "olist_rubric.json"
_CAUSAL = re.compile(
    r"\b(cause|causes|caused|because|sebep|sebebi)\b|root\s+cause|neden\s+oldu",
    re.I,
)


def _ops(result: dict[str, Any]) -> dict[str, dict]:
    return {e.get("operation"): e for e in result.get("evidence") or [] if e.get("operation")}


def score_case(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    ops = _ops(result)
    join = ops.get("join_assemble") or {}
    join_val = join.get("value") or {}
    assoc = ops.get("association_test") or {}
    gates = {
        "tables_joined": len(join_val.get("tables") or []) >= 2,
        "join_keys": {"order_id", "customer_id", "product_id"}.issubset(set(join_val.get("join_keys") or [])),
        "delay_derived": join_val.get("delay_column") == "delay_days" and join_val.get("derived_in_engine") is True,
        "review_bound": "review_score" in (assoc.get("source_columns") or [])
        or any("review" in json.dumps(e).lower() for e in result.get("evidence") or []),
        "evidence_object": bool(join) and bool(result.get("claims")),
        "no_causal_language": not _CAUSAL.search(json.dumps(result.get("claims") or [], ensure_ascii=False)),
        "no_margin_claim": "margin" not in json.dumps(result.get("claims") or []).lower()
        and "profit" not in json.dumps(result.get("claims") or []).lower(),
    }
    if item["id"] == "ol-gmv-review-category":
        gates["category_sql"] = "run_sql" in ops
    return {
        "id": item["id"],
        "decision": result.get("decision"),
        "gates": gates,
        "pass": all(gates.values()),
        "efficiency_row": overlay_row(
            case=item["id"],
            suite="olist",
            correct=all(gates.values()),
            evidence_valid=gate_evidence(result),
            result=result,
        ),
    }


def run_olist_rubric() -> dict[str, Any]:
    if not olist_available(OLIST_ROOT):
        return {"skipped": True, "reason": "Olist CSVs not in data/raw", "pass": True, "items": []}
    items = json.loads(RUBRIC.read_text(encoding="utf-8"))["items"]
    rows = []
    for item in items:
        result = run_investigation(OLIST_ROOT, item["question"])
        rows.append(score_case(item, result))
    return {
        "skipped": False,
        "pass": all(r["pass"] for r in rows),
        "n_pass": sum(1 for r in rows if r["pass"]),
        "n_scored": len(rows),
        "items": rows,
    }
