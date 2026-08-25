from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from analysis.evidence.log import EvidenceLog
from analysis.evidence.pipeline import _draft_claims
from analysis.evidence.validator import accepted_claims, validate_claim
from analysis.investigate import DRIVER_SHARE_MIN, NOISE_PCT
from analysis.load import load_tabular
from analysis.roles import column_with_semantic, columns_with_role
from analysis.tools.runtime import ToolContext, call_tool
from analysis.tools.schemas import CLOSED_TEMPLATES, Budget, Hypothesis, StopReason, TemplateId

WHY_CHANGE = "Satış neden değişti?"


def required_capabilities(question: str) -> set[str]:
    q = question.lower()
    if any(tok in q for tok in ("teslimat", "delivery", "gecikme", "kargo", "ship delay")):
        return {"delivery_analysis"}
    if any(tok in q for tok in ("retention", "tekrar satın", "repeat purchase")):
        return {"retention_analysis"}
    return {"temporal_analysis", "metric_comparison"}


def run_heuristic(
    path: str | Path,
    question: str = WHY_CHANGE,
    budget: Budget | None = None,
) -> dict[str, Any]:
    df = load_tabular(path)
    ctx = ToolContext(df=df, log=EvidenceLog(), budget=budget or Budget())
    ctx.budget.started_monotonic = time.monotonic()
    plan: list[str] = []
    hypotheses: list[Hypothesis] = []
    stop: StopReason | None = None
    decision = "abstain"
    primary_driver = None

    def step(name: str, **kwargs) -> Any:
        plan.append(name)
        return call_tool(ctx, name, **kwargs)

    step("inspect_dataset")
    step("profile_dataset")
    caps_res = step("detect_capabilities")
    roles = caps_res.extra.get("roles") if getattr(caps_res, "ok", False) else []
    flags = {}
    cap_ev = next((e for e in ctx.log if e.operation == "detect_capabilities"), None)
    if cap_ev and isinstance(cap_ev.value, dict):
        flags = cap_ev.value

    missing = [c for c in required_capabilities(question) if not flags.get(c)]
    if missing:
        stop = "abstain"
        hypotheses = []
    else:
        hypotheses = _rank_hypotheses(roles, ctx.budget)
        ctx.budget.hypotheses_used = len(hypotheses)
        stop, decision, primary_driver = _experiment_loop(ctx, hypotheses)
        if decision in {"primary_driver", "value_not_volume"}:
            step("create_chart", kind="trend")
            step("create_chart", kind="segment")

    step("generate_report")
    wrapped = _wrapped_ids(ctx)
    run = {
        "decision": decision,
        "primary_driver": primary_driver,
        "compare_periods": _payload(ctx, "compare_periods"),
        "coverage": _payload(ctx, "current_coverage"),
        "volume_value": _payload(ctx, "decompose_volume_value"),
        "interaction": _interaction_payload(ctx),
        "capabilities": _payload(ctx, "detect_capabilities"),
        "quality": _payload(ctx, "quality_score"),
    }
    drafts = _draft_claims(run, wrapped)
    validated = [validate_claim(c, ctx.log) for c in drafts]
    claims = accepted_claims(validated, ctx.log)
    return {
        "path": str(path),
        "question": question,
        "decision": decision,
        "primary_driver": primary_driver,
        "stop_reason": stop,
        "plan": plan,
        "hypotheses": [h.model_dump() for h in hypotheses],
        "evidence": [e.model_dump() for e in ctx.log.snapshot()],
        "claims": [c.model_dump() for c in claims],
        "charts": [c.model_dump() for c in ctx.charts],
        "traces": [t.model_dump() for t in ctx.traces],
        "budget": ctx.budget.model_dump(),
        "roles": roles,
        "capabilities": flags,
    }


def _over_budget(ctx: ToolContext) -> bool:
    b = ctx.budget
    if b.experiments_used >= b.max_experiments:
        return True
    if time.monotonic() - b.started_monotonic >= b.max_seconds:
        return True
    return False


def _rank_hypotheses(roles: list[dict], budget: Budget) -> list[Hypothesis]:
    dims = columns_with_role(roles, "dimension")
    region = column_with_semantic(roles, "region")
    product = next(
        (r["name"] for r in roles if r["role"] == "dimension" and r["semantic"] == "product"),
        None,
    )
    ranked: list[Hypothesis] = []

    def add(template: TemplateId, bindings: dict | None = None) -> None:
        if template not in CLOSED_TEMPLATES:
            raise ValueError(f"unknown template_id {template}")
        if len(ranked) >= budget.max_hypotheses:
            return
        ranked.append(
            Hypothesis(
                hypothesis_id=f"h-{len(ranked)+1:02d}",
                template_id=template,
                bindings=bindings or {},
                status="ranked",
            )
        )

    add("data_artefact")
    add("temporal_change")
    add("volume_vs_value")
    for dim in dims:
        add("segment_driver", {"dimension": dim})
    if region and product:
        add("interaction", {"dimensions": [region, product][: budget.max_interaction_depth]})
    add("anomaly")
    add("association")
    return ranked[: budget.max_hypotheses]


def _experiment_loop(
    ctx: ToolContext, hypotheses: list[Hypothesis]
) -> tuple[StopReason, str, str | None]:
    decision = "abstain"
    driver = None
    for hyp in hypotheses:
        if _over_budget(ctx):
            d, drv = _decide(ctx)
            return "budget", d, drv
        ctx.budget.experiments_used += 1
        result = call_tool(ctx, "test_hypothesis", hypothesis=hyp)
        hyp.status = "tested" if result.ok else "dropped"
        decision, driver = _decide(ctx)
        if decision == "data_artefact":
            return "abstain", decision, driver
        cmp = _last_value(ctx, "compare_periods")
        if (
            decision == "abstain"
            and cmp
            and cmp.get("change_pct") is not None
            and abs(cmp["change_pct"]) <= NOISE_PCT
        ):
            return "abstain", "abstain", None
        if decision in {"primary_driver", "value_not_volume"}:
            return "strong_evidence", decision, driver
    decision, driver = _decide(ctx)
    if decision == "abstain":
        return "abstain", decision, driver
    return "space_exhausted", decision, driver


def _decide(ctx: ToolContext) -> tuple[str, str | None]:
    cov = _last_value(ctx, "current_coverage")
    if cov and cov.get("truncated_current_period"):
        return "data_artefact", None
    cmp = _last_value(ctx, "compare_periods")
    if cmp:
        pct = cmp.get("change_pct")
        if pct is not None and abs(pct) <= NOISE_PCT:
            return "abstain", None
    vol = _last_value(ctx, "decompose_volume_value")
    if vol:
        aov = abs(vol.get("aov_change_pct") or 0)
        vchg = abs(vol.get("volume_change_pct") or 0)
        if aov >= 20 and vchg <= 10 and aov > vchg:
            return "value_not_volume", "AOV"
    interaction = _interaction_value(ctx)
    if interaction and interaction.get("rows"):
        top = interaction["rows"][0]
        share = abs(top.get("share_of_change") or 0)
        dims = (interaction.get("filters") or {}).get("dimensions") or []
        # filters live on evidence, not value
        ev = _last_evidence(ctx, "segment_by", two_dim=True)
        if ev:
            dims = (ev.filters or {}).get("dimensions") or dims
            top = (ev.value or {}).get("rows") or [{}]
            top = top[0] if top else {}
            share = abs(top.get("share_of_change") or 0)
            if share >= DRIVER_SHARE_MIN and len(dims) == 2:
                return "primary_driver", f"{top.get(dims[0])} × {top.get(dims[1])}"
    return "abstain", None


def _last_evidence(ctx: ToolContext, operation: str, two_dim: bool = False):
    items = [e for e in ctx.log if e.operation == operation]
    if two_dim:
        items = [e for e in items if len((e.filters or {}).get("dimensions") or []) == 2]
    return items[-1] if items else None


def _last_value(ctx: ToolContext, operation: str) -> dict | None:
    ev = _last_evidence(ctx, operation)
    return ev.value if ev and isinstance(ev.value, dict) else None


def _payload(ctx: ToolContext, operation: str) -> dict:
    ev = _last_evidence(ctx, operation)
    return ev.model_dump() if ev else {}


def _interaction_payload(ctx: ToolContext) -> dict:
    ev = _last_evidence(ctx, "segment_by", two_dim=True)
    return ev.model_dump() if ev else {}


def _interaction_value(ctx: ToolContext) -> dict | None:
    ev = _last_evidence(ctx, "segment_by", two_dim=True)
    return ev.value if ev and isinstance(ev.value, dict) else None


def _wrapped_ids(ctx: ToolContext) -> dict[str, str]:
    mapping = {
        "compare_periods": "compare_periods",
        "current_coverage": "coverage",
        "decompose_volume_value": "volume_value",
        "detect_capabilities": "capabilities",
        "quality_score": "quality",
    }
    wrapped: dict[str, str] = {}
    for op, key in mapping.items():
        ev = _last_evidence(ctx, op)
        if ev:
            wrapped[key] = ev.evidence_id
    inter = _last_evidence(ctx, "segment_by", two_dim=True)
    if inter:
        wrapped["interaction"] = inter.evidence_id
    return wrapped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evidra heuristic investigator (no LLM)")
    parser.add_argument("--data", required=True)
    parser.add_argument("--question", default=WHY_CHANGE)
    args = parser.parse_args(argv)
    result = run_heuristic(args.data, args.question)
    slim = {
        "decision": result["decision"],
        "primary_driver": result["primary_driver"],
        "stop_reason": result["stop_reason"],
        "plan": result["plan"],
        "claims": result["claims"],
    }
    print(json.dumps(slim, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
