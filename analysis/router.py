"""Deterministic chat turn router. Does not analyze tables or call tools."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from analysis.heuristic import required_capabilities

INTENTS = (
    "empty",
    "investigate",
    "answer_from_evidence",
    "follow_up_investigate",
    "abstain_capability",
    "show_steps",
    "show_report",
    "show_evidence",
)

CAPABILITY_ANSWERS = {
    "retention_analysis": (
        "Bu soruyu güvenilir biçimde yanıtlamak için müşteri kaybını temsil eden bir alan bulunmuyor."
    ),
    "delivery_analysis": (
        "Bu soruyu güvenilir biçimde yanıtlamak için teslimat gecikmesini temsil eden alanlar bulunmuyor."
    ),
    "causal_analysis": (
        "Bu soruyu güvenilir biçimde yanıtlamak için mevcut veri nedensel bir çözümlemeyi desteklemiyor."
    ),
    "multi_table_join": (
        "Bu soruyu güvenilir biçimde yanıtlamak için birden fazla tablonun birleştirilmesi gerekiyor; "
        "mevcut kaynakta bu yapı yok."
    ),
}

CAUSAL_LIMIT = "Mevcut veriler ilişkiyi gösteriyor ancak nedeni kesin olarak belirlemiyor."

_STEPS = re.compile(r"(ara[şs]t[ıi]rma ad[ıi]m|research step|ad[ıi]mlar[ıi]|plan[ıi]? g[öo]ster)", re.I)
_REPORT = re.compile(r"(detayl[ıi] rapor|detailed report|investigation report)", re.I)
_EVIDENCE = re.compile(
    r"(\bevidence\b|kan[ıi]tlar[ıi]|kan[ıi]t list|show evidence|evidence rapor)",
    re.I,
)
_DRILL = re.compile(r"(daha detay|detayl[ıi] incele|incele|g[öo]ster)", re.I)
_RANKING = re.compile(
    r"(en k[öo]t[üu]|en d[üu][şs][üu]k|en y[üu]ksek|hangi kategori|hangi b[öo]lge|"
    r"hangi segment|which region|worst category|top region)",
    re.I,
)
_CAUSAL_PROBE = re.compile(
    r"(bunun nedeni|nedeni ne\b|nedeni nedir|neden b[öo]yle|root cause|as[ıi]l neden)",
    re.I,
)
_ANAPHORA = re.compile(r"^\s*(peki|ya\b|peki ya|durum nas[ıi]l|bundan|o zaman)\b", re.I)
_SLICE = re.compile(r"\b(durum nas[ıi]l|nas[ıi]l bir tablo|orada ne var)\b", re.I)
_STATUS = re.compile(r"\b(durum nas[ıi]l|nas[ıi]l gidiyor|orada ne var)\b", re.I)
_SCOPED_WHY = re.compile(r"\b(neden|why)\b", re.I)
_DEEP_DRILL = re.compile(r"(daha detay|detayl[ıi] incele|ayr[ıi] incele|ayr[ıi] hipotez)", re.I)


class TurnDecision(BaseModel):
    intent: str
    reason: str = ""
    missing_capability: str | None = None
    focus_labels: list[str] = Field(default_factory=list)


def capability_flags(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    inner = raw.get("value") if isinstance(raw.get("value"), dict) else raw
    if any(k.endswith("_analysis") or k in {"segmentation", "association"} for k in inner):
        return inner
    return raw


def question_capabilities(question: str) -> set[str]:
    q = question.lower()
    if any(tok in q for tok in ("müşteri kayb", "musteri kayb", "churn", "kayıp müşteri", "kayip musteri")):
        return {"retention_analysis"}
    return required_capabilities(question)


def missing_capabilities(question: str, capabilities: dict[str, Any] | None) -> list[str]:
    flags = capability_flags(capabilities)
    if not flags:
        return []
    return [c for c in question_capabilities(question) if not flags.get(c)]


def capability_answer(capability: str) -> str:
    return CAPABILITY_ANSWERS.get(
        capability,
        "Bu soruyu güvenilir biçimde yanıtlamak için gerekli alan mevcut veride bulunmuyor.",
    )


def known_labels(run: dict[str, Any] | None) -> list[str]:
    if not run:
        return []
    labels: list[str] = []
    driver = run.get("primary_driver")
    if driver:
        labels.append(str(driver))
        labels.extend(part.strip() for part in re.split(r"\s*[×x]\s*", str(driver)) if part.strip())
    for ev in run.get("evidence") or []:
        if ev.get("operation") != "segment_by":
            continue
        for row in (ev.get("value") or {}).get("rows") or []:
            for key, val in row.items():
                if key in {"previous", "current", "change", "share_of_change"}:
                    continue
                text = str(val).strip()
                if text and text not in labels:
                    labels.append(text)
    return labels


def mentioned_labels(text: str, run: dict[str, Any] | None) -> list[str]:
    if not run:
        return []
    lower = text.lower()
    return [lab for lab in known_labels(run) if lab.lower() in lower]


def is_causal_probe(text: str) -> bool:
    return bool(_CAUSAL_PROBE.search(text))


def is_ranking_question(text: str) -> bool:
    return bool(_RANKING.search(text))


def route_turn(
    text: str,
    *,
    has_run: bool,
    last_run: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> TurnDecision:
    t = text.strip()
    if not t:
        return TurnDecision(intent="empty", reason="empty")

    if has_run:
        if _STEPS.search(t):
            return TurnDecision(intent="show_steps", reason="meta_steps")
        if _REPORT.search(t):
            return TurnDecision(intent="show_report", reason="meta_report")
        if _EVIDENCE.search(t):
            return TurnDecision(intent="show_evidence", reason="meta_evidence")

    missing = missing_capabilities(t, capabilities)
    if missing:
        return TurnDecision(
            intent="abstain_capability",
            reason="missing_capability",
            missing_capability=missing[0],
        )

    if not has_run:
        return TurnDecision(intent="investigate", reason="no_prior_run")

    labels = mentioned_labels(t, last_run)
    if labels and _STATUS.search(t):
        return TurnDecision(intent="answer_from_evidence", reason="existing_slice", focus_labels=labels)
    if labels and not is_ranking_question(t) and (_SCOPED_WHY.search(t) or _DEEP_DRILL.search(t)):
        return TurnDecision(intent="follow_up_investigate", reason="scoped_why", focus_labels=labels)
    if is_causal_probe(t):
        return TurnDecision(intent="answer_from_evidence", reason="causal_probe", focus_labels=labels)
    if is_ranking_question(t):
        return TurnDecision(intent="answer_from_evidence", reason="ranking", focus_labels=labels)
    if labels:
        return TurnDecision(intent="answer_from_evidence", reason="existing_slice", focus_labels=labels)
    if _ANAPHORA.search(t) or _SLICE.search(t):
        return TurnDecision(intent="answer_from_evidence", reason="anaphora", focus_labels=labels)
    if _DRILL.search(t):
        return TurnDecision(intent="answer_from_evidence", reason="drill", focus_labels=labels)
    return TurnDecision(intent="investigate", reason="new_question")
