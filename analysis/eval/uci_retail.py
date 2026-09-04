"""V2.7 retail line-item adapter eval. Process rubric, not a numeric city golden."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from analysis.eval.efficiency import overlay_row
from analysis.eval.runner import STOP_OK, gate_evidence
from analysis.graph import run_investigation

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data" / "fixtures" / "retail_line_items.csv"
CATALOG = ROOT / "evals" / "uci_retail.json"
_CAUSAL = re.compile(
    r"\b(cause|causes|caused|because|sebep|sebebi)\b|root\s+cause|neden\s+oldu",
    re.I,
)


def _ops(result: dict[str, Any]) -> dict[str, dict]:
    return {e.get("operation"): e for e in result.get("evidence") or [] if e.get("operation")}


def _check(name: str, result: dict[str, Any]) -> bool:
    ops = _ops(result)
    roles = result.get("roles") or []
    caps = result.get("capabilities") or {}
    if name == "metric_amount":
        return any(r.get("name") == "amount" and r.get("semantic") == "sales" for r in roles)
    if name == "time_invoice_date":
        return any(r.get("role") == "time" and "date" in str(r.get("name", "")).lower() for r in roles)
    if name == "compare_periods":
        return "compare_periods" in ops
    if name == "country_dimension":
        return any(r.get("name") == "Country" and r.get("role") == "dimension" for r in roles)
    if name == "segment_country":
        for ev in result.get("evidence") or []:
            if ev.get("operation") != "segment_by":
                continue
            dims = (ev.get("filters") or {}).get("dimensions") or []
            if any(str(d).lower() == "country" for d in dims):
                return True
        return False
    if name == "volume_value":
        return "decompose_volume_value" in ops
    if name == "canonicalize_amount":
        can = ops.get("canonicalize") or {}
        return "amount" in ((can.get("value") or {}).get("derived_columns") or [])
    if name == "dropped_cancelled":
        can = ops.get("canonicalize") or {}
        return int((can.get("value") or {}).get("dropped_cancelled_or_negative") or 0) >= 1
    if name == "abstain":
        return result.get("decision") == "abstain"
    if name == "hypotheses_empty":
        return not result.get("hypotheses")
    if name == "evidence_valid":
        return gate_evidence(result)
    if name == "completeness":
        return result.get("stop_reason") in STOP_OK
    if name == "no_causal":
        return not _CAUSAL.search(json.dumps(result.get("claims") or [], ensure_ascii=False))
    if name == "reviews_present":
        return bool(result.get("reviews"))
    if name == "plan_review":
        return "review_claims" in (result.get("plan") or [])
    if name == "no_delivery_capability":
        return caps.get("delivery_analysis") is False
    return False


def score_case(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    gates = {c: _check(c, result) for c in item.get("checks") or []}
    ok = all(gates.values()) if gates else False
    return {
        "id": item["id"],
        "decision": result.get("decision"),
        "stop_reason": result.get("stop_reason"),
        "gates": gates,
        "pass": ok,
        "efficiency_row": overlay_row(
            case=item["id"],
            suite="uci_retail",
            correct=ok,
            evidence_valid=gate_evidence(result),
            result=result,
        ),
    }


def run_uci_retail() -> dict[str, Any]:
    if not FIXTURE.exists():
        return {"skipped": True, "reason": "retail_line_items.csv missing", "pass": True, "items": []}
    items = json.loads(CATALOG.read_text(encoding="utf-8"))["items"]
    cache: dict[str, dict[str, Any]] = {}
    rows = []
    for item in items:
        q = item["question"]
        if q not in cache:
            cache[q] = run_investigation(FIXTURE, q)
        rows.append(score_case(item, cache[q]))
    return {
        "skipped": False,
        "pass": all(r["pass"] for r in rows),
        "n_pass": sum(1 for r in rows if r["pass"]),
        "n_scored": len(rows),
        "items": rows,
    }
