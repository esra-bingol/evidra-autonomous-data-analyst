"""V2.4 Adaptive Research: closed-template follow-ups with an explicit reason.

No new tools, no ReAct, no extra agent. Sufficiency is a heuristic over frozen
evidence. Budget exhaustion yields abstain, not a fabricated driver.
"""

from __future__ import annotations

from typing import Any

from analysis.heuristic import (
    _decide,
    _interaction_value,
    _last_evidence,
    _last_value,
    _over_budget,
)
from analysis.investigate import DRIVER_SHARE_MIN, NOISE_PCT
from analysis.tools.runtime import ToolContext, call_tool
from analysis.tools.schemas import CLOSED_TEMPLATES, Hypothesis

# Unique cell at DRIVER_SHARE_MIN is enough to *claim* in V1. Competing cells
# at that threshold are not a unique driver — that is the adaptive trigger.


def competing_driver_labels(ctx: ToolContext) -> list[str]:
    ev = _last_evidence(ctx, "segment_by", two_dim=True)
    if ev is None:
        return []
    dims = list((ev.filters or {}).get("dimensions") or [])
    rows = list((ev.value or {}).get("rows") or [])
    if len(dims) < 2:
        return []
    labels: list[str] = []
    for row in rows:
        share = abs(float(row.get("share_of_change") or 0))
        if share >= DRIVER_SHARE_MIN:
            labels.append(f"{row.get(dims[0])} × {row.get(dims[1])}")
    return labels


def _noise_abstain(ctx: ToolContext, intent: str, decision: str) -> bool:
    if intent == "ranking" or decision != "abstain":
        return False
    cmp = _last_value(ctx, "compare_periods")
    if not cmp or cmp.get("change_pct") is None:
        return False
    return abs(float(cmp["change_pct"])) <= NOISE_PCT


def assess_sufficiency(
    state: dict[str, Any], ctx: ToolContext, hyps: list
) -> dict[str, Any]:
    intent = state.get("intent") or "why_change"
    decision = state.get("decision") or "abstain"
    driver = state.get("primary_driver")
    stop = state.get("stop_reason") or ""
    steps = list(state.get("research_steps") or [])
    adaptive_used = int((ctx.budget.adaptive_steps_used or 0))
    max_adapt = int(getattr(ctx.budget, "max_adaptive_steps", 4) or 0)

    if state.get("skip_experiments"):
        return {
            "sufficient": True,
            "insufficient_kind": None,
            "pending_reason": None,
            "research_steps": steps,
        }
    if stop == "budget":
        return {
            "sufficient": True,
            "insufficient_kind": "budget",
            "pending_reason": None,
            "research_steps": steps,
        }
    if decision == "data_artefact":
        return {"sufficient": True, "insufficient_kind": None, "pending_reason": None, "research_steps": steps}
    if decision in {"ranking", "association", "value_not_volume"}:
        return {"sufficient": True, "insufficient_kind": None, "pending_reason": None, "research_steps": steps}
    if _noise_abstain(ctx, intent, decision):
        return {"sufficient": True, "insufficient_kind": None, "pending_reason": None, "research_steps": steps}

    competing = competing_driver_labels(ctx)
    if len(competing) >= 2:
        reason = (
            f"{competing[0]} and {competing[1]} each meet the driver-share threshold. "
            "A unique primary driver is not established. Test the next closed template."
        )
        nxt = _next_ranked(hyps)
        if nxt is None or adaptive_used >= max_adapt or _over_budget(ctx):
            kind = "multiple_plausible_drivers"
            stop_reason = "abstain"
            if _over_budget(ctx) and nxt is not None:
                kind = "budget"
                stop_reason = "budget"
            elif adaptive_used >= max_adapt and nxt is not None:
                kind = "budget"
                stop_reason = "budget"
            return {
                "sufficient": True,
                "decision": "abstain",
                "primary_driver": None,
                "stop_reason": stop_reason,
                "insufficient_kind": kind,
                "pending_reason": None,
                "research_steps": steps,
            }
        nxt.reason = reason
        return {
            "sufficient": False,
            "insufficient_kind": "multiple_plausible_drivers",
            "pending_reason": reason,
            "research_steps": steps,
        }

    if decision == "primary_driver" and driver:
        if _last_value(ctx, "decompose_volume_value") is None:
            reason = (
                f"{driver} explains most of the decline, but this does not establish "
                "whether the decline is driven by fewer orders or lower AOV. "
                "Investigate volume versus value."
            )
            nxt = _ensure_template(hyps, "volume_vs_value", reason)
            if nxt is not None and adaptive_used < max_adapt and not _over_budget(ctx):
                return {
                    "sufficient": False,
                    "insufficient_kind": "needs_decomposition",
                    "pending_reason": reason,
                    "research_steps": steps,
                }
        return {
            "sufficient": True,
            "insufficient_kind": None,
            "pending_reason": None,
            "research_steps": steps,
        }

    remaining = _next_ranked(hyps)
    if remaining is not None and decision == "abstain" and adaptive_used < max_adapt and not _over_budget(ctx):
        reason = (
            "Current evidence does not sufficiently support the question. "
            "Run the next closed-template experiment."
        )
        remaining.reason = reason
        return {
            "sufficient": False,
            "insufficient_kind": "unanswered_question",
            "pending_reason": reason,
            "research_steps": steps,
        }

    return {
        "sufficient": True,
        "insufficient_kind": None,
        "pending_reason": None,
        "research_steps": steps,
    }


def _next_ranked(hyps: list) -> Hypothesis | None:
    for i, item in enumerate(hyps):
        hyp = item if isinstance(item, Hypothesis) else Hypothesis.model_validate(item)
        hyps[i] = hyp
        if hyp.status == "ranked":
            return hyp
    return None


def _ensure_template(hyps: list, template_id: str, reason: str) -> Hypothesis | None:
    if template_id not in CLOSED_TEMPLATES:
        return None
    existing = _next_ranked(hyps)
    if existing is not None:
        existing.reason = reason
        return existing
    for hyp in hyps:
        tid = hyp.template_id if isinstance(hyp, Hypothesis) else hyp.get("template_id")
        status = hyp.status if isinstance(hyp, Hypothesis) else hyp.get("status")
        if tid == template_id and status == "tested":
            return None
    extra = Hypothesis(
        hypothesis_id=f"h-adapt-{len(hyps)+1:02d}",
        template_id=template_id,  # type: ignore[arg-type]
        bindings={},
        status="ranked",
        reason=reason,
    )
    hyps.append(extra)
    return extra


def run_next_step(state: dict[str, Any]) -> dict[str, Any]:
    ctx: ToolContext = state["ctx"]
    hyps = list(state.get("hypotheses") or [])
    reason = state.get("pending_reason") or "Follow-up experiment required."
    kind = state.get("insufficient_kind") or "unanswered_question"
    steps = list(state.get("research_steps") or [])
    intent = state.get("intent") or "why_change"

    if _over_budget(ctx) or ctx.budget.adaptive_steps_used >= ctx.budget.max_adaptive_steps:
        return {
            "plan": state.get("plan") or [],
            "hypotheses": hyps,
            "decision": "abstain",
            "primary_driver": None,
            "stop_reason": "budget",
            "sufficient": True,
            "insufficient_kind": "budget",
            "pending_reason": None,
            "research_steps": steps,
        }

    hyp = _next_ranked(hyps)
    if hyp is None:
        return {
            "plan": state.get("plan") or [],
            "hypotheses": hyps,
            "decision": "abstain",
            "primary_driver": None,
            "stop_reason": state.get("stop_reason") or "abstain",
            "sufficient": True,
            "insufficient_kind": kind,
            "pending_reason": None,
            "research_steps": steps,
        }

    # Keep the object in the list in sync (dict vs model).
    for i, item in enumerate(hyps):
        hid = item.hypothesis_id if isinstance(item, Hypothesis) else item.get("hypothesis_id")
        if hid == hyp.hypothesis_id:
            if isinstance(item, Hypothesis):
                item.reason = hyp.reason or reason
                hyp = item
            else:
                hyp.reason = hyp.reason or reason
                hyps[i] = hyp
            break
    else:
        hyp.reason = hyp.reason or reason
        hyps.append(hyp)

    ctx.budget.experiments_used += 1
    ctx.budget.adaptive_steps_used += 1
    result = call_tool(ctx, "test_hypothesis", hypothesis=hyp)
    hyp.status = "tested" if result.ok else "dropped"
    decision, driver = _decide(ctx, intent)
    steps.append(
        {
            "reason": hyp.reason or reason,
            "kind": kind,
            "template_id": hyp.template_id,
            "hypothesis_id": hyp.hypothesis_id,
            "ok": bool(result.ok),
        }
    )
    return {
        "plan": state.get("plan") or [],
        "hypotheses": hyps,
        "decision": decision,
        "primary_driver": driver,
        "stop_reason": state.get("stop_reason") or "strong_evidence",
        "research_steps": steps,
        "pending_reason": None,
        "budget": ctx.budget.model_dump(),
    }
