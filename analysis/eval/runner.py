from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from analysis.evidence.log import EvidenceLog
from analysis.evidence.models import Claim
from analysis.evidence.validator import validate_claim
from analysis.graph import run_investigation
from analysis.load import load_tabular
from analysis.periods import compare_periods
from analysis.tools.schemas import Budget

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "evals" / "golden.json"
DATASETS = {
    "clear_driver": ROOT / "data" / "fixtures" / "clear_driver.csv",
    "aov_trap": ROOT / "data" / "fixtures" / "aov_trap.csv",
    "no_signal": ROOT / "data" / "fixtures" / "no_signal.csv",
    "missingness": ROOT / "data" / "fixtures" / "missingness.csv",
    "superstore": ROOT / "data" / "raw" / "superstore.csv",
}
STOP_OK = frozenset({"strong_evidence", "space_exhausted", "budget", "abstain"})
_CAUSAL = re.compile(
    r"\b(cause|causes|caused|because|sebep|sebebi)\b|root\s+cause|neden\s+oldu",
    re.I,
)
_FAKE_CONF = re.compile(r"\b\d+(\.\d+)?\s*%\s*(confidence|güven)\b", re.I)


def load_golden() -> list[dict[str, Any]]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))["items"]


def run_item(item: dict[str, Any]) -> dict[str, Any]:
    path = DATASETS[item["dataset_id"]]
    if item.get("optional") and not path.exists():
        return {"skipped": True, "reason": f"{path} missing"}
    kwargs: dict[str, Any] = {}
    if item.get("budget"):
        kwargs["budget"] = Budget(**item["budget"])
    t0 = time.monotonic()
    result = run_investigation(path, item["question"], **kwargs)
    elapsed = (time.monotonic() - t0) * 1000
    efficiency = {
        "item_id": item["id"],
        "n_traces": len(result.get("traces") or []),
        "n_hypotheses": len(result.get("hypotheses") or []),
        "n_evidence": len(result.get("evidence") or []),
        "duration_ms": round(elapsed, 2),
        "token_cost": None,
    }
    return {"skipped": False, "result": result, "efficiency": efficiency}


def _change_pct(result: dict[str, Any]) -> float | None:
    for ev in result.get("evidence") or []:
        if ev.get("operation") == "compare_periods":
            val = ev.get("value") or {}
            if val.get("change_pct") is not None:
                return float(val["change_pct"])
    return None


def gate_correctness(item: dict[str, Any], result: dict[str, Any]) -> bool:
    exp = item.get("expected") or {}
    if "decision" in exp and result.get("decision") != exp["decision"]:
        return False
    if "primary_driver" in exp and result.get("primary_driver") != exp["primary_driver"]:
        return False
    if exp.get("hypotheses_empty") and result.get("hypotheses"):
        return False
    if "stop_reason" in exp and result.get("stop_reason") != exp["stop_reason"]:
        return False
    if "change_pct_band" in exp:
        pct = _change_pct(result)
        lo, hi = exp["change_pct_band"]
        if pct is None or not (lo <= pct <= hi):
            return False
    return True


def gate_evidence(result: dict[str, Any]) -> bool:
    claims = result.get("claims") or []
    ids = {e.get("evidence_id") for e in result.get("evidence") or []}
    for claim in claims:
        if not claim.get("provenance_ok", True):
            return False
        kind = claim.get("kind")
        eids = claim.get("evidence_ids") or []
        if kind in {"association", "ranking", "quality"}:
            if not eids:
                return False
            if any(eid not in ids for eid in eids):
                return False
    return True


def gate_completeness(result: dict[str, Any]) -> bool:
    return result.get("stop_reason") in STOP_OK


def gate_language(item: dict[str, Any], result: dict[str, Any]) -> bool:
    blob = json.dumps(result.get("claims") or [], ensure_ascii=False)
    if _CAUSAL.search(blob) or _FAKE_CONF.search(blob):
        return False
    lowered = blob.lower()
    for tok in item.get("forbidden_language") or []:
        if tok.lower() in lowered:
            return False
    return True


def score_item(item: dict[str, Any], packed: dict[str, Any]) -> dict[str, Any]:
    if packed.get("skipped"):
        return {"id": item["id"], "skipped": True, "reason": packed.get("reason"), "pass": True}
    result = packed["result"]
    gates = {
        "correctness": gate_correctness(item, result),
        "evidence": gate_evidence(result),
        "completeness": gate_completeness(result),
        "forbidden_language": gate_language(item, result),
    }
    return {
        "id": item["id"],
        "metric_type": item["metric_type"],
        "skipped": False,
        "gates": gates,
        "pass": all(gates.values()),
        "efficiency": packed["efficiency"],
        "decision": result.get("decision"),
        "stop_reason": result.get("stop_reason"),
        "primary_driver": result.get("primary_driver"),
    }


def run_suite() -> dict[str, Any]:
    rows = []
    efficiency_log = []
    for item in load_golden():
        packed = run_item(item)
        scored = score_item(item, packed)
        rows.append(scored)
        if scored.get("efficiency"):
            efficiency_log.append(scored["efficiency"])
    gated = [r for r in rows if not r.get("skipped")]
    return {
        "n_items": len(rows),
        "n_scored": len(gated),
        "n_pass": sum(1 for r in gated if r["pass"]),
        "pass": all(r["pass"] for r in gated),
        "items": rows,
        "efficiency_log": efficiency_log,
    }


def hallucination_is_caught() -> bool:
    """Injected unbound figure must fail the evidence lock (not an agent run)."""
    df = load_tabular(DATASETS["clear_driver"])
    log = EvidenceLog()
    ev = log.append_result(compare_periods(df))
    fake = Claim(
        claim_id="poison",
        text="Sales fell 99.0%.",
        kind="association",
        evidence_ids=[ev.evidence_id],
    )
    return validate_claim(fake, log).provenance_ok is False
