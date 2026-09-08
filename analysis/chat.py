"""V2.5 conversational layer. Does not analyze tables; it only starts or summarizes investigations.

User text never becomes SQL or Python. Follow-ups read the last run's frozen evidence.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from analysis.graph import run_investigation
from analysis.response import compose_response

_DETAIL = re.compile(
    r"(ad[ıi]m|steps?|plan|evidence|kan[ıi]t|rapor|detay|incele|g[öo]ster|daha|"
    r"neden böyle|how did you)",
    re.I,
)
_STEPS = re.compile(r"(ara[şs]t[ıi]rma ad[ıi]m|research step|ad[ıi]mlar[ıi]|plan[ıi]? g[öo]ster)", re.I)
_REPORT = re.compile(r"(detayl[ıi] rapor|detailed report|investigation report)", re.I)
_EVIDENCE = re.compile(r"(evidence|kan[ıi]t|evidence rapor)", re.I)
_INVESTIGATE = re.compile(
    r"(sat[ıi][şs].*(neden|d[üu][şs]|de[ğg]i[şs])|why did sales|what drove|hangi b[öo]lge|"
    r"teslimat|delivery|gecikme|k[âa]r|profit|retention|tekrar)",
    re.I,
)
_DRILL = re.compile(r"(daha detay|detayl[ıi] incele|incele|g[öo]ster)", re.I)


def classify_turn(text: str, has_run: bool) -> str:
    t = text.strip()
    if not t:
        return "empty"
    if not has_run:
        return "investigate"
    if _STEPS.search(t):
        return "show_steps"
    if _REPORT.search(t):
        return "show_report"
    if _EVIDENCE.search(t):
        return "show_evidence"
    if _DRILL.search(t) and not _INVESTIGATE.search(t):
        return "focus_existing"
    if _INVESTIGATE.search(t):
        return "investigate"
    if _DETAIL.search(t):
        return "focus_existing"
    return "investigate"


def _change_pct(run: dict[str, Any]) -> float | None:
    for ev in run.get("evidence") or []:
        if ev.get("operation") == "compare_periods":
            val = ev.get("value") or {}
            if val.get("change_pct") is not None:
                return float(val["change_pct"])
    return None


def _known_labels(run: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    driver = run.get("primary_driver")
    if driver:
        labels.append(str(driver))
        labels.extend(part.strip() for part in str(driver).replace("×", " ").split() if part.strip())
    for ev in run.get("evidence") or []:
        if ev.get("operation") != "segment_by":
            continue
        for row in (ev.get("value") or {}).get("rows") or []:
            for key in ("region", "category"):
                val = row.get(key)
                if val and str(val) not in labels:
                    labels.append(str(val))
    return labels


def _mentioned_labels(text: str, run: dict[str, Any]) -> list[str]:
    lower = text.lower()
    hits = [lab for lab in _known_labels(run) if lab.lower() in lower]
    return hits


def _claim_ids(run: dict[str, Any]) -> list[str]:
    return [c.get("claim_id") for c in (run.get("claims") or []) if isinstance(c, dict) and c.get("claim_id")]


def _evidence_ids_from_claims(run: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for claim in run.get("claims") or []:
        for eid in claim.get("evidence_ids") or []:
            if eid not in ids:
                ids.append(eid)
    return ids


def summarize_run(run: dict[str, Any]) -> str:
    return compose_response(run).answer


def _focus_text(run: dict[str, Any], message: str) -> str:
    labels = _mentioned_labels(message, run) or (
        [run["primary_driver"]] if run.get("primary_driver") else []
    )
    lines = []
    if labels:
        lines.append("Mevcut inceleme state'inden devam: " + ", ".join(labels) + ".")
    else:
        lines.append("Yeni bir dataset taraması yok; son incelemenin evidence'ına bakıyorum.")
    for ev in run.get("evidence") or []:
        if ev.get("operation") != "segment_by":
            continue
        rows = (ev.get("value") or {}).get("rows") or []
        picked = []
        for row in rows:
            blob = " ".join(str(v) for v in row.values())
            if labels and not any(lab in blob for lab in labels):
                continue
            picked.append(row)
            if len(picked) >= 4:
                break
        if picked:
            eid = ev.get("evidence_id")
            lines.append(f"segment_by ({eid}):")
            for row in picked:
                lines.append(
                    f"  {row.get('region', '')} {row.get('category', '')} "
                    f"change={row.get('change')} share={row.get('share_of_change')}"
                )
    steps = run.get("research_steps") or []
    if steps:
        lines.append("Kayıtlı follow-up reason: " + (steps[0].get("reason") or "")[:240])
    if len(lines) == 1:
        claims = run.get("claims") or []
        if claims:
            lines.append(claims[0].get("text") or "")
    lines.append("Bu bir özet; sayılar son run evidence'ından. Yeni SQL üretilmedi.")
    return "\n".join(lines)


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


InvestigateFn = Callable[[str, str], dict[str, Any]]


def default_investigate(path: str, question: str) -> dict[str, Any]:
    return run_investigation(path, question)


def handle_message(
    *,
    text: str,
    dataset_path: str,
    last_run: dict[str, Any] | None,
    investigate: InvestigateFn = default_investigate,
) -> dict[str, Any]:
    """Return assistant turn. Never executes the raw message as SQL/Python."""
    intent = classify_turn(text, has_run=bool(last_run and not last_run.get("error")))
    if intent == "empty":
        return {
            "role": "assistant",
            "text": "Bir iş sorusu yazın. Metin SQL veya Python olarak çalıştırılmaz.",
            "intent": intent,
            "ran_investigation": False,
            "run_id": (last_run or {}).get("id"),
            "claim_ids": [],
            "evidence_ids": [],
            "status": None,
        }

    if intent == "investigate":
        result = investigate(dataset_path, text.strip())
        contract = compose_response(result)
        status = {
            "decision": result.get("decision"),
            "stop_reason": result.get("stop_reason"),
            "primary_driver": result.get("primary_driver"),
        }
        return {
            "role": "assistant",
            "text": contract.answer,
            "response": contract.model_dump(),
            "intent": intent,
            "ran_investigation": True,
            "run": result,
            "run_id": result.get("id"),
            "claim_ids": _claim_ids(result),
            "evidence_ids": _evidence_ids_from_claims(result),
            "status": status,
        }

    assert last_run is not None
    status = {
        "decision": last_run.get("decision"),
        "stop_reason": last_run.get("stop_reason"),
        "primary_driver": last_run.get("primary_driver"),
    }
    if intent == "show_steps":
        body = _steps_text(last_run)
    elif intent == "show_report":
        body = (
            "Detaylı rapor mevcut investigation state’ten üretildi; yeni claim yok. "
            "Chat kısa kalır; rapor evidence, plan, reviewer ve grafikleri taşır."
        )
    elif intent == "show_evidence":
        body = _evidence_text(last_run)
    else:
        body = _focus_text(last_run, text)
    out = {
        "role": "assistant",
        "text": body,
        "intent": intent,
        "ran_investigation": False,
        "run_id": last_run.get("id"),
        "claim_ids": _claim_ids(last_run),
        "evidence_ids": _evidence_ids_from_claims(last_run),
        "status": status,
    }
    if intent == "show_report" and last_run.get("id"):
        out["report_url"] = f"/report?run={last_run['id']}"
    return out
