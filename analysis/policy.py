from __future__ import annotations

from typing import Any

from analysis.tools.schemas import CLOSED_TEMPLATES, Budget, Hypothesis


class UnknownTemplateError(ValueError):
    """LLM/policy proposed a template_id outside the closed set."""


def detect_intent(question: str) -> str:
    q = question.lower()
    if any(tok in q for tok in ("teslimat", "delivery", "gecikme", "kargo", "ship delay")):
        return "delivery"
    if any(tok in q for tok in ("retention", "tekrar satın", "repeat purchase", "tekrar alım")):
        return "retention"
    if any(
        tok in q
        for tok in ("rank", "ranking", "en yüksek", "hangi bölge", "top region", "sırala")
    ):
        return "ranking"
    if any(tok in q for tok in ("review", "puan", "review score")):
        return "association"
    return "why_change"


def apply_llm_rank(
    raw: list[dict[str, Any]],
    roles: list[dict],
    budget: Budget,
) -> list[Hypothesis]:
    """Allowlist only. Unknown template_id fails the run."""
    legal_cols = {r["name"] for r in roles}
    ranked: list[Hypothesis] = []
    for item in raw:
        tid = item.get("template_id")
        if tid not in CLOSED_TEMPLATES:
            raise UnknownTemplateError(str(tid))
        if item.get("skip"):
            continue
        bindings = dict(item.get("bindings") or {})
        for col in _binding_columns(bindings):
            if col not in legal_cols:
                raise ValueError(f"binding column not in role table: {col}")
        ranked.append(
            Hypothesis(
                hypothesis_id=f"h-{len(ranked)+1:02d}",
                template_id=tid,  # type: ignore[arg-type]
                bindings=bindings,
                status="ranked",
                selected_by="llm",
            )
        )
        if len(ranked) >= budget.max_hypotheses:
            break
    return ranked


def _binding_columns(bindings: dict[str, Any]) -> list[str]:
    cols: list[str] = []
    if isinstance(bindings.get("dimension"), str):
        cols.append(bindings["dimension"])
    dims = bindings.get("dimensions")
    if isinstance(dims, list):
        cols.extend(str(d) for d in dims)
    return cols


def silent_llm_fallback() -> bool:
    """No API key → heuristic; never crash the graph."""
    import os

    return not (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
