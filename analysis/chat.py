"""V2.5 conversational layer. Does not analyze tables; it only starts or summarizes investigations.

User text never becomes SQL or Python. Follow-ups read the last run's frozen evidence.
"""

from __future__ import annotations

from typing import Any, Callable

from analysis.graph import run_investigation
from analysis.report import build_investigation_report
from analysis.response import compose_followup, compose_response, compose_scoped
from analysis.router import capability_answer, route_turn
from analysis.scope import apply_scope, resolve_scope
from analysis.load import load_source

InvestigateFn = Callable[..., dict[str, Any]]


def classify_turn(
    text: str,
    has_run: bool,
    capabilities: dict[str, Any] | None = None,
    last_run: dict[str, Any] | None = None,
) -> str:
    return route_turn(
        text,
        has_run=has_run,
        last_run=last_run,
        capabilities=capabilities,
    ).intent


def summarize_run(run: dict[str, Any]) -> str:
    return compose_response(run).answer


def _claim_ids(run: dict[str, Any]) -> list[str]:
    return [c.get("claim_id") for c in (run.get("claims") or []) if isinstance(c, dict) and c.get("claim_id")]


def _evidence_ids_from_claims(run: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for claim in run.get("claims") or []:
        for eid in claim.get("evidence_ids") or []:
            if eid not in ids:
                ids.append(eid)
    return ids


def _steps_text(run: dict[str, Any]) -> str:
    plan = run.get("plan") or []
    steps = run.get("research_steps") or []
    hyps = run.get("hypotheses") or []
    lines = [f"Plan: {' → '.join(plan)}"]
    if hyps:
        first = hyps[0]
        lines.append(f"İlk hipotez: {first.get('template_id')} ({first.get('status')})")
    for step in steps:
        lines.append(f"Next: {step.get('template_id')} — {step.get('reason')}")
    if not steps:
        lines.append("Adaptive follow-up yok; ilk tur yeterli sayıldı.")
    return "\n".join(lines)


def _evidence_text(run: dict[str, Any]) -> str:
    rows = []
    for ev in (run.get("evidence") or [])[:12]:
        rows.append(f"{ev.get('evidence_id')} · {ev.get('operation')} · {ev.get('strength')}")
    if not rows:
        return "Bu run'da evidence yok."
    return "Evidence (son run):\n" + "\n".join(rows)


def default_investigate(
    path: str, question: str, scope: dict[str, str] | None = None
) -> dict[str, Any]:
    return run_investigation(path, question, scope=scope)


def _call_investigate(
    investigate: InvestigateFn, path: str, question: str, scope: dict[str, str] | None = None
) -> dict[str, Any]:
    try:
        return investigate(path, question, scope=scope)
    except TypeError:
        return investigate(path, question)


def _status(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not run:
        return None
    return {
        "decision": run.get("decision"),
        "stop_reason": run.get("stop_reason"),
        "primary_driver": run.get("primary_driver"),
    }


def _assistant(
    *,
    text: str,
    intent: str,
    last_run: dict[str, Any] | None,
    ran: bool = False,
    response: dict[str, Any] | None = None,
    run: dict[str, Any] | None = None,
    missing_capability: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = run or last_run or {}
    out = {
        "role": "assistant",
        "text": text,
        "intent": intent,
        "ran_investigation": ran,
        "run_id": source.get("id"),
        "claim_ids": _claim_ids(source) if source else [],
        "evidence_ids": _evidence_ids_from_claims(source) if source else [],
        "status": _status(source),
    }
    if response is not None:
        out["response"] = response
        if response.get("evidence_refs"):
            out["evidence_ids"] = response["evidence_refs"]
    if run is not None:
        out["run"] = run
        out["run_id"] = run.get("id")
        out["claim_ids"] = _claim_ids(run)
        out["evidence_ids"] = _evidence_ids_from_claims(run)
        out["status"] = _status(run)
    if missing_capability:
        out["missing_capability"] = missing_capability
    if extra:
        out.update(extra)
    return out


def handle_message(
    *,
    text: str,
    dataset_path: str,
    last_run: dict[str, Any] | None,
    capabilities: dict[str, Any] | None = None,
    investigate: InvestigateFn = default_investigate,
) -> dict[str, Any]:
    """Return assistant turn. Never executes the raw message as SQL/Python."""
    usable = last_run if last_run and not last_run.get("error") else None
    caps = capabilities if capabilities is not None else (usable or {}).get("capabilities")
    decision = route_turn(text, has_run=bool(usable), last_run=usable, capabilities=caps)
    intent = decision.intent

    if intent == "empty":
        return _assistant(
            text="Bir iş sorusu yazın. Metin SQL veya Python olarak çalıştırılmaz.",
            intent=intent,
            last_run=last_run,
        )

    if intent == "abstain_capability":
        cap = decision.missing_capability or "retention_analysis"
        answer = capability_answer(cap)
        return _assistant(
            text=answer,
            intent=intent,
            last_run=usable,
            missing_capability=cap,
            response={"answer": answer, "key_findings": [], "evidence_refs": [], "limitations": [answer], "suggested_followups": []},
        )

    if intent == "investigate":
        result = _call_investigate(investigate, dataset_path, text.strip())
        contract = compose_response(result)
        return _assistant(
            text=contract.answer,
            intent=intent,
            last_run=usable,
            ran=True,
            response=contract.model_dump(),
            run=result,
        )

    if intent == "follow_up_investigate":
        scope = resolve_scope(usable, decision.focus_labels)
        if not scope or usable is None:
            contract = compose_followup(usable or {}, text)
            return _assistant(
                text=contract.answer,
                intent="answer_from_evidence",
                last_run=usable,
                response=contract.model_dump(),
            )
        try:
            preview = apply_scope(load_source(dataset_path).df, scope)
        except ValueError:
            preview = None
        if preview is None or len(preview) == 0:
            contract = compose_followup(usable, text)
            return _assistant(
                text=contract.answer,
                intent="answer_from_evidence",
                last_run=usable,
                response=contract.model_dump(),
            )
        result = _call_investigate(investigate, dataset_path, text.strip(), scope=scope)
        result["parent_run_id"] = usable.get("id")
        result["scope"] = scope
        result["investigation_report"] = build_investigation_report(result)
        contract = compose_scoped(result, scope)
        return _assistant(
            text=contract.answer,
            intent=intent,
            last_run=usable,
            ran=True,
            response=contract.model_dump(),
            run=result,
            extra={"parent_run_id": usable.get("id"), "scope": scope},
        )

    assert usable is not None
    if intent == "show_steps":
        body = _steps_text(usable)
        return _assistant(text=body, intent=intent, last_run=usable)
    if intent == "show_report":
        extra = {}
        if usable.get("id"):
            extra["report_url"] = f"/report?run={usable['id']}"
        return _assistant(
            text=(
                "Detaylı rapor mevcut investigation state’ten üretildi; yeni claim yok. "
                "Chat kısa kalır; rapor evidence, plan, reviewer ve grafikleri taşır."
            ),
            intent=intent,
            last_run=usable,
            extra=extra,
        )
    if intent == "show_evidence":
        return _assistant(text=_evidence_text(usable), intent=intent, last_run=usable)

    contract = compose_followup(usable, text)
    return _assistant(
        text=contract.answer,
        intent="answer_from_evidence",
        last_run=usable,
        response=contract.model_dump(),
    )
