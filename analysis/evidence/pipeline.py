from __future__ import annotations

from typing import Any

from analysis.evidence.log import EvidenceLog
from analysis.evidence.models import Chart, Claim
from analysis.evidence.validator import accepted_claims, validate_claim
from analysis.investigate import investigate
from analysis.result import EngineResult

_WRAP_KEYS = (
    "compare_periods",
    "coverage",
    "volume_value",
    "interaction",
    "capabilities",
    "quality",
)


def lock_investigation(path: str) -> dict[str, Any]:
    """Wrap a Phase 2 run as Evidence and validated Claims. No new analysis."""
    run = investigate(path)
    log = EvidenceLog()
    wrapped: dict[str, str] = {}
    for key in _WRAP_KEYS:
        payload = run.get(key)
        if not payload:
            continue
        ev = log.append_result(payload)
        wrapped[key] = ev.evidence_id

    charts = _lock_charts(run.get("charts") or [], wrapped)
    drafts = _draft_claims(run, wrapped)
    validated = [validate_claim(c, log) for c in drafts]
    return {
        "path": run["path"],
        "decision": run["decision"],
        "primary_driver": run["primary_driver"],
        "evidence": [e.model_dump() for e in log.snapshot()],
        "claims": [c.model_dump() for c in accepted_claims(validated, log)],
        "rejected_claims": [c.model_dump() for c in validated if not c.provenance_ok],
        "charts": [c.model_dump() for c in charts],
        "evidence_ids": wrapped,
    }


def _lock_charts(raw_charts: list[dict], wrapped: dict[str, str]) -> list[Chart]:
    ids: list[str] = []
    for key in ("compare_periods", "interaction", "volume_value"):
        if key in wrapped:
            ids.append(wrapped[key])
    if not ids:
        raise ValueError("chart requires evidence")
    charts: list[Chart] = []
    for raw in raw_charts:
        value = raw.get("value") or {}
        plotly = value.get("plotly") if isinstance(value, dict) else None
        kind = value.get("kind") if isinstance(value, dict) else raw.get("operation")
        if not plotly:
            continue
        charts.append(Chart(kind=str(kind or "chart"), plotly=plotly, evidence_ids=list(ids)))
    return charts


def _draft_claims(run: dict[str, Any], wrapped: dict[str, str]) -> list[Claim]:
    decision = run["decision"]
    driver = run["primary_driver"]
    cmp = (run.get("compare_periods") or {}).get("value") or {}
    pct = cmp.get("change_pct")
    claims: list[Claim] = []

    if decision == "primary_driver" and driver and "interaction" in wrapped:
        text = (
            f"The sales change ({pct}%) is associated with {driver} "
            f"as the leading share of period change."
        )
        claims.append(
            Claim(
                claim_id="cl-001",
                text=text,
                kind="association",
                evidence_ids=[wrapped["compare_periods"], wrapped["interaction"]],
            )
        )
    elif decision == "value_not_volume" and "volume_value" in wrapped:
        aov = ((run.get("volume_value") or {}).get("value") or {}).get("aov_change_pct")
        vol = ((run.get("volume_value") or {}).get("value") or {}).get("volume_change_pct")
        text = (
            f"The sales change ({pct}%) is associated with AOV ({aov}%) "
            f"rather than order volume ({vol}%)."
        )
        claims.append(
            Claim(
                claim_id="cl-001",
                text=text,
                kind="association",
                evidence_ids=[wrapped["compare_periods"], wrapped["volume_value"]],
            )
        )
    elif decision == "data_artefact" and "coverage" in wrapped:
        last = ((run.get("coverage") or {}).get("value") or {}).get("current_last_observed")
        if pct is None:
            text = (
                f"Observed truncated current period (last observed {last}); "
                "treat as a data artefact."
            )
        else:
            text = (
                f"The apparent sales change ({pct}%) co-occurs with a truncated current period "
                f"(last observed {last}); treat as a data artefact."
            )
        eids = [wrapped["coverage"]]
        if "compare_periods" in wrapped:
            eids.append(wrapped["compare_periods"])
        claims.append(
            Claim(
                claim_id="cl-001",
                text=text,
                kind="quality",
                evidence_ids=eids,
            )
        )
    elif decision == "abstain":
        claims.append(
            Claim(
                claim_id="cl-001",
                text=(
                    "No concentrated association is supported; the result is inconclusive "
                    "(capability intersection does not justify a driver claim)."
                ),
                kind="abstention",
                evidence_ids=[],
            )
        )
    return claims


def wrap_engine_result(result: EngineResult, log: EvidenceLog) -> str:
    return log.append_result(result).evidence_id
