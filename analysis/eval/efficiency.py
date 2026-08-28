"""V2.3 efficiency measurement. Does not change the investigation engine.

Correctness always outranks efficiency. A cheap wrong answer is not a win.
Thresholds are derived from measured golden behaviour, not a hard-coded cap.
The efficiency gate is proposed, not enforced, in this slice.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any

from analysis.evidence.validator import _CAUSAL

SETUP_TOOLS = frozenset(
    {"inspect_dataset", "profile_dataset", "detect_capabilities", "create_chart", "generate_report"}
)
EXPERIMENT_TOOLS = frozenset({"test_hypothesis"})
EXECUTED = frozenset({"tested", "dropped"})


def reviewer_valid(result: dict[str, Any]) -> bool:
    reviews = result.get("reviews") or []
    claims = result.get("claims") or []
    if _CAUSAL.search(json.dumps(reviews, ensure_ascii=False)):
        return False
    by_id = {r.get("claim_id"): r for r in reviews if isinstance(r, dict)}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        verdict = by_id.get(claim.get("claim_id"))
        if reviews and verdict is None:
            return False
        if verdict and verdict.get("decision") == "reject":
            return False
        if verdict and verdict.get("decision") not in {"accept", "revise", "abstain"}:
            return False
    return True


def measure_run(
    result: dict[str, Any],
    *,
    duration_ms: float | None = None,
    token_cost: Any = None,
) -> dict[str, Any]:
    traces = result.get("traces") or []
    hyps = result.get("hypotheses") or []
    evidence = result.get("evidence") or []
    budget = result.get("budget") or {}

    exp_traces = [t for t in traces if t.get("tool") in EXPERIMENT_TOOLS]
    executed_hyps = [h for h in hyps if isinstance(h, dict) and h.get("status") in EXECUTED]

    seen: set[tuple[str, str]] = set()
    redundant = 0
    for hyp in executed_hyps:
        key = (
            str(hyp.get("template_id") or ""),
            json.dumps(hyp.get("bindings") or {}, sort_keys=True, default=str),
        )
        if key in seen:
            redundant += 1
        else:
            seen.add(key)

    ops = [e.get("operation") for e in evidence if isinstance(e, dict) and e.get("operation")]
    duplicate_ops = sum(n - 1 for n in Counter(ops).values() if n > 1)

    interaction_depth = 0
    for hyp in executed_hyps:
        if hyp.get("template_id") != "interaction":
            continue
        dims = (hyp.get("bindings") or {}).get("dimensions") or []
        interaction_depth = max(interaction_depth, len(dims))

    experiments_used = budget.get("experiments_used")
    if experiments_used is None:
        experiments_used = len(exp_traces)

    return {
        "total_tool_calls": len(traces),
        "setup_tool_calls": sum(1 for t in traces if t.get("tool") in SETUP_TOOLS),
        "total_experiments": int(experiments_used),
        "hypotheses_generated": len(hyps),
        "hypotheses_executed": len(executed_hyps),
        "hypotheses_untested": sum(1 for h in hyps if isinstance(h, dict) and h.get("status") == "ranked"),
        "redundant_experiments": redundant,
        "successful_evidence_experiments": sum(1 for t in exp_traces if t.get("ok")),
        "rejected_experiments": sum(1 for h in executed_hyps if h.get("status") == "dropped")
        + sum(1 for t in exp_traces if not t.get("ok")),
        "investigation_depth": len(executed_hyps),
        "interaction_depth": interaction_depth,
        "duplicate_evidence_operations": duplicate_ops,
        "duration_ms": duration_ms,
        "token_cost": token_cost,
    }


def overlay_row(
    *,
    case: str,
    suite: str,
    correct: bool,
    evidence_valid: bool,
    result: dict[str, Any],
    duration_ms: float | None = None,
    token_cost: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = measure_run(result, duration_ms=duration_ms, token_cost=token_cost)
    review_ok = reviewer_valid(result)
    eligible = bool(correct and evidence_valid and review_ok)
    if not eligible:
        efficiency = "blocked"
        reason = _block_reason(correct, evidence_valid, review_ok)
    else:
        efficiency = (
            f"{metrics['hypotheses_executed']}/{metrics['hypotheses_generated']} exec, "
            f"{metrics['redundant_experiments']} redundant"
        )
        reason = None
    row = {
        "case": case,
        "suite": suite,
        "correct": correct,
        "evidence_valid": evidence_valid,
        "reviewer_valid": review_ok,
        "tool_calls": metrics["total_tool_calls"],
        "experiments": metrics["total_experiments"],
        "redundant": metrics["redundant_experiments"],
        "efficiency": efficiency,
        "efficiency_eligible": eligible,
        "block_reason": reason,
        "metrics": metrics,
    }
    if extra:
        row.update(extra)
    return row


def _block_reason(correct: bool, evidence_valid: bool, review_ok: bool) -> str:
    if not correct:
        return "correctness"
    if not evidence_valid:
        return "evidence"
    if not review_ok:
        return "reviewer"
    return "efficiency"


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    idx = (len(xs) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return float(xs[lo])
    w = idx - lo
    return float(xs[lo] * (1.0 - w) + xs[hi] * w)


def propose_thresholds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive caps from measured *correct* golden runs. Exclude the forced-budget item."""
    eligible = [
        r
        for r in rows
        if r.get("suite") == "golden"
        and r.get("efficiency_eligible")
        and r.get("case") != "ev-b1"
    ]
    experiments = [float(r["experiments"]) for r in eligible]
    tool_calls = [float(r["tool_calls"]) for r in eligible]
    redundant = [float(r["redundant"]) for r in eligible]
    by_type: dict[str, list[float]] = defaultdict(list)
    for row in eligible:
        by_type[str(row.get("metric_type") or "unknown")].append(float(row["experiments"]))
    per_type = {
        kind: {
            "n": len(vals),
            "max": max(vals),
            "p50": _percentile(vals, 0.5),
            "p95": _percentile(vals, 0.95),
            "proposed_max_experiments": int(math.ceil(max(vals))),
        }
        for kind, vals in sorted(by_type.items())
    }
    max_exp = max(experiments) if experiments else None
    max_tools = max(tool_calls) if tool_calls else None
    return {
        "enforced": False,
        "basis": "golden efficiency-eligible rows except ev-b1 (forced max_experiments=1)",
        "n_basis": len(eligible),
        "experiments": {
            "p50": _percentile(experiments, 0.5),
            "p95": _percentile(experiments, 0.95),
            "max": max_exp,
            "proposed_max": None if max_exp is None else int(math.ceil(max_exp)),
        },
        "tool_calls": {
            "p50": _percentile(tool_calls, 0.5),
            "p95": _percentile(tool_calls, 0.95),
            "max": max_tools,
            "proposed_max": None if max_tools is None else int(math.ceil(max_tools)),
        },
        "redundant_experiments": {
            "max": max(redundant) if redundant else None,
            "proposed_max": int(max(redundant)) if redundant else 0,
        },
        "by_metric_type": per_type,
        "rule": (
            "Flag (do not fail correctness) if a future golden-correct run exceeds "
            "the observed max experiments or tool calls for its metric_type, or has "
            "redundant_experiments above the observed max. Never prefer a cheaper incorrect run."
        ),
    }


def flag_against_proposal(row: dict[str, Any], proposal: dict[str, Any]) -> str | None:
    if not row.get("efficiency_eligible"):
        return None
    if row.get("case") == "ev-b1":
        return None
    kind = row.get("metric_type")
    per = (proposal.get("by_metric_type") or {}).get(kind) if kind else None
    cap = (per or {}).get("proposed_max_experiments")
    if cap is not None and row["experiments"] > cap:
        return f"experiments {row['experiments']} > proposed_max {cap} for {kind}"
    red_cap = (proposal.get("redundant_experiments") or {}).get("proposed_max")
    if red_cap is not None and row["redundant"] > red_cap:
        return f"redundant {row['redundant']} > proposed_max {red_cap}"
    tools_cap = (proposal.get("tool_calls") or {}).get("proposed_max")
    if tools_cap is not None and row["suite"] == "golden" and row["tool_calls"] > tools_cap:
        return f"tool_calls {row['tool_calls']} > proposed_max {tools_cap}"
    return None


def collect_rows(
    golden: dict[str, Any],
    olist: dict[str, Any] | None = None,
    adversarial: dict[str, Any] | None = None,
    adaptive: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in golden.get("items") or []:
        row = item.get("efficiency_row")
        if row:
            rows.append(row)
    for item in (olist or {}).get("items") or []:
        row = item.get("efficiency_row")
        if row:
            rows.append(row)
    for item in (adversarial or {}).get("items") or []:
        row = item.get("efficiency_row")
        if row:
            rows.append(row)
    for item in (adaptive or {}).get("items") or []:
        row = item.get("efficiency_row")
        if row:
            rows.append(row)
    return rows


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    proposal = propose_thresholds(rows)
    for row in rows:
        row["efficiency_flag"] = flag_against_proposal(row, proposal)
    table = [
        {
            "case": r["case"],
            "suite": r["suite"],
            "correct": r["correct"],
            "evidence_valid": r["evidence_valid"],
            "reviewer_valid": r["reviewer_valid"],
            "tool_calls": r["tool_calls"],
            "experiments": r["experiments"],
            "redundant": r["redundant"],
            "efficiency": r["efficiency"],
        }
        for r in rows
    ]
    return {
        "efficiency_enforced": False,
        "gate_order": ["correctness", "evidence_valid", "reviewer_valid", "efficiency"],
        "proposed_thresholds": proposal,
        "n_blocked": sum(1 for r in rows if not r["efficiency_eligible"]),
        "n_eligible": sum(1 for r in rows if r["efficiency_eligible"]),
        "n_flagged": sum(1 for r in rows if r.get("efficiency_flag")),
        "table": table,
        "items": rows,
    }


def run_efficiency() -> dict[str, Any]:
    from analysis.eval.adversarial import run_adversarial
    from analysis.eval.olist_rubric import run_olist_rubric
    from analysis.eval.runner import run_suite

    golden = run_suite()
    olist = run_olist_rubric()
    adversarial = run_adversarial()
    return build_report(collect_rows(golden, olist, adversarial))


def main(argv: list[str] | None = None) -> None:
    del argv
    report = run_efficiency()
    slim = {
        "efficiency_enforced": report["efficiency_enforced"],
        "gate_order": report["gate_order"],
        "proposed_thresholds": report["proposed_thresholds"],
        "n_eligible": report["n_eligible"],
        "n_blocked": report["n_blocked"],
        "table": report["table"],
    }
    print(json.dumps(slim, indent=2, ensure_ascii=False))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
