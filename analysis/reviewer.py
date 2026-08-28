from __future__ import annotations

import re
from typing import Any

from analysis.evidence.models import Claim, Evidence, ReviewVerdict
from analysis.evidence.validator import (
    FACTUAL_KINDS,
    _CAUSAL,
    _FAKE_CONFIDENCE,
    _numbers_supported,
)

_PRIMARY = re.compile(
    r"primary\s+driver|birincil\s+sürücü|\bdrove\b|\bdrives\b|caused the decline",
    re.I,
)
_WEAK = frozenset({"weak", "inconclusive"})
DRIVER_DECISIONS = frozenset({"primary_driver", "value_not_volume"})


def review_claims(
    claims: list[Claim],
    evidence: list[Evidence] | list[dict[str, Any]],
    decision: str,
    stop_reason: str | None = None,
) -> list[ReviewVerdict]:
    """Audit claims against a frozen evidence snapshot. No tools, no log writes."""
    items = [_as_evidence(e) for e in evidence]
    by_id = {e.evidence_id: e for e in items}
    return [_review_one(c, by_id, decision, stop_reason or "") for c in claims]


def publish_claims(claims: list[Claim], verdicts: list[ReviewVerdict]) -> list[Claim]:
    by_id = {v.claim_id: v for v in verdicts}
    out: list[Claim] = []
    for claim in claims:
        v = by_id.get(claim.claim_id)
        if v is None or v.decision == "reject":
            continue
        if v.decision == "revise" and v.recommended_claim:
            out.append(claim.model_copy(update={"text": v.recommended_claim, "provenance_ok": True}))
            continue
        if v.decision in {"accept", "abstain", "revise"}:
            out.append(claim)
    return out


def _as_evidence(e: Evidence | dict[str, Any]) -> Evidence:
    if isinstance(e, Evidence):
        return e
    return Evidence.model_validate(e)


def _review_one(
    claim: Claim,
    by_id: dict[str, Evidence],
    decision: str,
    stop_reason: str,
) -> ReviewVerdict:
    issues = _lock_issues(claim, by_id)
    bound = [by_id[i] for i in claim.evidence_ids if i in by_id]
    rec_strength = _max_strength(bound)

    if issues:
        return ReviewVerdict(
            claim_id=claim.claim_id,
            decision="reject",
            reason="Claim is not supported by the evidence lock.",
            issues=issues,
            recommended_strength=rec_strength,
        )

    if claim.kind == "abstention":
        if decision == "abstain" or stop_reason == "abstain":
            return ReviewVerdict(
                claim_id=claim.claim_id,
                decision="accept",
                reason="Abstention matches insufficient evidence.",
                recommended_strength="inconclusive",
            )
        return ReviewVerdict(
            claim_id=claim.claim_id,
            decision="reject",
            reason="Abstention claim while the run asserted a finding.",
            issues=["abstention_mismatch"],
            recommended_strength=rec_strength,
        )

    if _PRIMARY.search(claim.text) and decision not in DRIVER_DECISIONS:
        if _drove_only(claim.text):
            revised = _CAUSAL.sub("", claim.text)
            revised = re.sub(r"\bdrove\b|\bdrives\b", "is associated with", revised, flags=re.I)
            return ReviewVerdict(
                claim_id=claim.claim_id,
                decision="revise",
                reason="Driver wording is stronger than the run decision; association language only.",
                issues=["overclaim"],
                recommended_strength=rec_strength,
                recommended_claim=revised.strip(),
            )
        return ReviewVerdict(
            claim_id=claim.claim_id,
            decision="reject",
            reason="Primary-driver wording is not supported by the run decision.",
            issues=["overclaim"],
            recommended_strength=rec_strength,
        )

    if _PRIMARY.search(claim.text) and rec_strength in _WEAK:
        return ReviewVerdict(
            claim_id=claim.claim_id,
            decision="reject",
            reason="Driver claim is stronger than bound evidence strength.",
            issues=["strength_mismatch"],
            recommended_strength=rec_strength,
        )

    if stop_reason == "budget" and claim.kind in FACTUAL_KINDS and not bound:
        return ReviewVerdict(
            claim_id=claim.claim_id,
            decision="reject",
            reason="Budget stop with no bound evidence for a factual claim.",
            issues=["missing_evidence"],
        )

    return ReviewVerdict(
        claim_id=claim.claim_id,
        decision="accept",
        reason="Claim is supported by evidence.",
        recommended_strength=rec_strength,
    )


def _drove_only(text: str) -> bool:
    return bool(re.search(r"\bdrove\b|\bdrives\b", text, re.I)) and not _CAUSAL.search(text)


def _lock_issues(claim: Claim, by_id: dict[str, Evidence]) -> list[str]:
    issues: list[str] = []
    if _CAUSAL.search(claim.text):
        issues.append("causal_language")
    if _FAKE_CONFIDENCE.search(claim.text):
        issues.append("fake_confidence")
    if claim.kind in FACTUAL_KINDS and not claim.evidence_ids:
        issues.append("missing_evidence")
    missing = [eid for eid in claim.evidence_ids if eid not in by_id]
    if missing:
        issues.append("unknown_evidence_id")
    if claim.kind in FACTUAL_KINDS and claim.evidence_ids and not missing:
        values = [by_id[eid].value for eid in claim.evidence_ids]
        if not _numbers_supported(claim.text, values):
            issues.append("unbound_number")
    return issues


def _max_strength(items: list[Evidence]) -> str | None:
    order = {"inconclusive": 0, "weak": 1, "moderate": 2, "strong": 3}
    if not items:
        return None
    return max((e.strength for e in items), key=lambda s: order.get(s, 0))
