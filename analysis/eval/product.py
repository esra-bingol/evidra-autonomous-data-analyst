"""V2.14 product questions. Process rubric across taxi + optional Superstore/Olist."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from analysis.eval.efficiency import overlay_row
from analysis.eval.runner import STOP_OK, gate_evidence
from analysis.graph import run_investigation
from analysis.olist import olist_available

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "evals" / "product.json"
_CAUSAL = re.compile(
    r"\b(cause|causes|caused|because|sebep|sebebi)\b|root\s+cause|neden\s+oldu",
    re.I,
)

DATASETS = {
    "taxi_trips": ROOT / "data" / "fixtures" / "taxi_trips.csv",
    "superstore": ROOT / "data" / "raw" / "superstore.csv",
    "olist": ROOT / "data" / "raw",
}


def _flatten_numbers(obj: Any) -> list[float]:
    out: list[float] = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_flatten_numbers(v))
        return out
    if isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_flatten_numbers(v))
    return out


def _check(name: str, result: dict[str, Any]) -> bool:
    ops = {e.get("operation") for e in result.get("evidence") or []}
    caps = result.get("capabilities") or {}
    if name == "compare_periods":
        return "compare_periods" in ops
    if name == "segment_borough":
        for ev in result.get("evidence") or []:
            if ev.get("operation") != "segment_by":
                continue
            dims = (ev.get("filters") or {}).get("dimensions") or []
            if any("borough" in str(d).lower() or "region" in str(d).lower() for d in dims):
                return True
        return False
    if name == "ranking":
        return result.get("decision") == "ranking"
    if name == "abstain":
        return result.get("decision") == "abstain"
    if name == "hypotheses_empty":
        return not result.get("hypotheses")
    if name == "completeness":
        return result.get("stop_reason") in STOP_OK
    if name == "evidence_valid":
        return gate_evidence(result)
    if name == "no_causal":
        blob = json.dumps(
            {
                "claims": result.get("claims") or [],
                "summary": (result.get("investigation_report") or {}).get("executive_summary"),
            },
            ensure_ascii=False,
        )
        return not _CAUSAL.search(blob)
    if name == "no_delivery_capability":
        return caps.get("delivery_analysis") is False
    if name == "association_or_abstain":
        return result.get("decision") in {"association", "abstain"}
    if name == "charts_bound":
        viz = (result.get("investigation_report") or {}).get("visualizations") or []
        evid_ids = {e.get("evidence_id") for e in result.get("evidence") or []}
        pool = _flatten_numbers([e.get("value") for e in result.get("evidence") or []])
        for ch in viz:
            if not set(ch.get("evidence_ids") or []) <= evid_ids:
                return False
            ys = []
            for trace in (ch.get("plotly") or {}).get("data") or []:
                ys.extend(_flatten_numbers(trace.get("y")))
            for y in ys:
                if not any(abs(y - n) < 1e-6 for n in pool):
                    return False
        return True
    return False


def _dataset_path(name: str) -> Path | None:
    path = DATASETS.get(name)
    if path is None:
        return None
    if name == "olist":
        return path if olist_available(path) else None
    return path if path.exists() else None


def score_case(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    gates = {c: _check(c, result) for c in item.get("checks") or []}
    ok = all(gates.values()) if gates else False
    return {
        "id": item["id"],
        "dataset": item.get("dataset"),
        "decision": result.get("decision"),
        "stop_reason": result.get("stop_reason"),
        "gates": gates,
        "pass": ok,
        "skipped": False,
        "efficiency_row": overlay_row(
            case=item["id"],
            suite="product",
            correct=ok,
            evidence_valid=gate_evidence(result),
            result=result,
        ),
    }


def run_product(*, include_optional: bool = True) -> dict[str, Any]:
    items = json.loads(CATALOG.read_text(encoding="utf-8"))["items"]
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    rows = []
    skipped = []
    for item in items:
        if item.get("optional") and not include_optional:
            skipped.append(item["id"])
            rows.append(
                {
                    "id": item["id"],
                    "dataset": item["dataset"],
                    "skipped": True,
                    "pass": True,
                    "gates": {},
                }
            )
            continue
        path = _dataset_path(item["dataset"])
        if path is None:
            skipped.append(item["id"])
            rows.append(
                {
                    "id": item["id"],
                    "dataset": item["dataset"],
                    "skipped": True,
                    "pass": True,
                    "gates": {},
                }
            )
            continue
        key = (item["dataset"], item["question"])
        if key not in cache:
            cache[key] = run_investigation(path, item["question"])
        rows.append(score_case(item, cache[key]))
    scored = [r for r in rows if not r.get("skipped")]
    return {
        "skipped": not scored,
        "pass": all(r["pass"] for r in rows),
        "n_pass": sum(1 for r in scored if r["pass"]),
        "n_scored": len(scored),
        "n_skipped": len(skipped),
        "skipped_ids": skipped,
        "items": rows,
    }
