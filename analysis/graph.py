from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from analysis.evidence.log import EvidenceLog
from analysis.evidence.pipeline import _draft_claims
from analysis.evidence.validator import accepted_claims, validate_claim
from analysis.heuristic import (
    WHY_CHANGE,
    _experiment_loop,
    _interaction_payload,
    _payload,
    _rank_hypotheses,
    _wrapped_ids,
    required_capabilities,
)
from analysis.load import load_source
from analysis.policy import apply_llm_rank, detect_intent, silent_llm_fallback
from analysis.tools.runtime import ToolContext, call_tool
from analysis.tools.schemas import Budget


class GraphState(TypedDict, total=False):
    path: str
    question: str
    intent: str
    policy: str
    llm_rank: list[dict[str, Any]] | None
    plan: list[str]
    hypotheses: list
    decision: str
    primary_driver: str | None
    stop_reason: str | None
    skip_experiments: bool
    claims: list
    evidence: list
    traces: list
    charts: list
    roles: list
    capabilities: dict
    budget: dict
    ctx: ToolContext


def _step(state: GraphState, name: str, **kwargs: Any) -> None:
    state.setdefault("plan", [])
    state["plan"].append(name)
    call_tool(state["ctx"], name, **kwargs)


def inspect_node(state: GraphState) -> dict:
    _step(state, "inspect_dataset")
    return {"plan": state["plan"]}


def profile_node(state: GraphState) -> dict:
    _step(state, "profile_dataset")
    return {"plan": state["plan"]}


def capabilities_node(state: GraphState) -> dict:
    res = call_tool(state["ctx"], "detect_capabilities")
    state.setdefault("plan", []).append("detect_capabilities")
    roles = res.extra.get("roles") if getattr(res, "ok", False) else []
    flags: dict = {}
    cap_ev = next((e for e in state["ctx"].log if e.operation == "detect_capabilities"), None)
    if cap_ev and isinstance(cap_ev.value, dict):
        flags = cap_ev.value
    return {"plan": state["plan"], "roles": roles, "capabilities": flags}


def intersect_node(state: GraphState) -> dict:
    state.setdefault("plan", []).append("intersect")
    flags = state.get("capabilities") or {}
    missing = [c for c in required_capabilities(state["question"]) if not flags.get(c)]
    if missing:
        return {
            "plan": state["plan"],
            "skip_experiments": True,
            "hypotheses": [],
            "stop_reason": "abstain",
            "decision": "abstain",
            "primary_driver": None,
        }
    return {"plan": state["plan"], "skip_experiments": False}


def rank_node(state: GraphState) -> dict:
    state.setdefault("plan", []).append("rank_hypotheses")
    ctx = state["ctx"]
    intent = state.get("intent") or detect_intent(state["question"])
    roles = state.get("roles") or []
    raw = state.get("llm_rank")
    policy = state.get("policy") or "heuristic"
    if policy == "llm" and raw is not None:
        hyps = apply_llm_rank(raw, roles, ctx.budget)
    elif policy == "llm" and silent_llm_fallback():
        hyps = _rank_hypotheses(roles, ctx.budget, intent)
    else:
        hyps = _rank_hypotheses(roles, ctx.budget, intent)
    ctx.budget.hypotheses_used = len(hyps)
    return {"plan": state["plan"], "hypotheses": hyps, "intent": intent}


def experiment_node(state: GraphState) -> dict:
    state.setdefault("plan", []).append("experiment_loop")
    hyps = list(state.get("hypotheses") or [])
    stop, decision, driver = _experiment_loop(
        state["ctx"], hyps, state.get("intent") or "why_change"
    )
    return {
        "plan": state["plan"],
        "hypotheses": hyps,
        "stop_reason": stop,
        "decision": decision,
        "primary_driver": driver,
    }


def score_node(state: GraphState) -> dict:
    state.setdefault("plan", []).append("score")
    return {"plan": state["plan"]}


def stop_node(state: GraphState) -> dict:
    state.setdefault("plan", []).append("stop")
    ctx = state["ctx"]
    decision = state.get("decision")
    if decision in {"primary_driver", "value_not_volume", "ranking"}:
        call_tool(ctx, "create_chart", kind="trend")
        call_tool(ctx, "create_chart", kind="segment")
    stop = state.get("stop_reason") or "abstain"
    return {"plan": state["plan"], "stop_reason": stop, "budget": ctx.budget.model_dump()}


def validate_node(state: GraphState) -> dict:
    state.setdefault("plan", []).append("validate_claims")
    ctx = state["ctx"]
    call_tool(ctx, "generate_report")
    wrapped = _wrapped_ids(ctx)
    run = {
        "decision": state.get("decision") or "abstain",
        "primary_driver": state.get("primary_driver"),
        "compare_periods": _payload(ctx, "compare_periods"),
        "coverage": _payload(ctx, "current_coverage"),
        "volume_value": _payload(ctx, "decompose_volume_value"),
        "interaction": _interaction_payload(ctx),
        "capabilities": _payload(ctx, "detect_capabilities"),
        "quality": _payload(ctx, "quality_score"),
        "association_test": _payload(ctx, "association_test"),
        "join_assemble": _payload(ctx, "join_assemble"),
        "run_sql": _payload(ctx, "run_sql"),
    }
    drafts = _draft_claims(run, wrapped)
    validated = [validate_claim(c, ctx.log) for c in drafts]
    claims = accepted_claims(validated, ctx.log)
    return {
        "plan": state["plan"],
        "claims": [c.model_dump() for c in claims],
        "evidence": [e.model_dump() for e in ctx.log.snapshot()],
        "traces": [t.model_dump() for t in ctx.traces],
        "charts": [c.model_dump() for c in ctx.charts],
    }


def report_node(state: GraphState) -> dict:
    state.setdefault("plan", []).append("report")
    return {"plan": state["plan"]}


def _route_intersect(state: GraphState) -> str:
    return "validate_claims" if state.get("skip_experiments") else "rank_hypotheses"


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("inspect", inspect_node)
    g.add_node("profile", profile_node)
    g.add_node("detect_capabilities", capabilities_node)
    g.add_node("intersect", intersect_node)
    g.add_node("rank_hypotheses", rank_node)
    g.add_node("experiment_loop", experiment_node)
    g.add_node("score", score_node)
    g.add_node("stop", stop_node)
    g.add_node("validate_claims", validate_node)
    g.add_node("report", report_node)
    g.add_edge(START, "inspect")
    g.add_edge("inspect", "profile")
    g.add_edge("profile", "detect_capabilities")
    g.add_edge("detect_capabilities", "intersect")
    g.add_conditional_edges(
        "intersect",
        _route_intersect,
        {"validate_claims": "validate_claims", "rank_hypotheses": "rank_hypotheses"},
    )
    g.add_edge("rank_hypotheses", "experiment_loop")
    g.add_edge("experiment_loop", "score")
    g.add_edge("score", "stop")
    g.add_edge("stop", "validate_claims")
    g.add_edge("validate_claims", "report")
    g.add_edge("report", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_investigation(
    path: str | Path,
    question: str = WHY_CHANGE,
    budget: Budget | None = None,
    policy: str = "heuristic",
    llm_rank: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    src = load_source(path)
    ctx = ToolContext(
        df=src.df,
        log=EvidenceLog(),
        budget=budget or Budget(),
        tables=src.tables,
        catalog_meta=src.meta,
    )
    ctx.budget.started_monotonic = time.monotonic()
    initial: GraphState = {
        "path": str(path),
        "question": question,
        "intent": detect_intent(question),
        "policy": policy,
        "llm_rank": llm_rank,
        "plan": [],
        "hypotheses": [],
        "decision": "abstain",
        "primary_driver": None,
        "skip_experiments": False,
        "ctx": ctx,
    }
    final = get_graph().invoke(initial)
    hyps = final.get("hypotheses") or []
    return {
        "path": str(path),
        "question": question,
        "decision": final.get("decision") or "abstain",
        "primary_driver": final.get("primary_driver"),
        "stop_reason": final.get("stop_reason"),
        "plan": final.get("plan") or [],
        "hypotheses": [h.model_dump() if hasattr(h, "model_dump") else h for h in hyps],
        "evidence": final.get("evidence") or [],
        "claims": final.get("claims") or [],
        "charts": final.get("charts") or [],
        "traces": final.get("traces") or [],
        "budget": final.get("budget") or ctx.budget.model_dump(),
        "roles": final.get("roles") or [],
        "capabilities": final.get("capabilities") or {},
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evidra LangGraph investigation (heuristic fallback)")
    parser.add_argument("--data", required=True)
    parser.add_argument("--question", default=WHY_CHANGE)
    args = parser.parse_args(argv)
    result = run_investigation(args.data, args.question)
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
