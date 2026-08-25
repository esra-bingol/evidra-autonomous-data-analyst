from __future__ import annotations

import re
from typing import Any, Iterable

from analysis.evidence.log import EvidenceLog
from analysis.evidence.models import Claim

_CAUSAL = re.compile(
    r"\b(cause|causes|caused|because|sebep|sebebi)\b|root\s+cause|neden\s+oldu",
    re.IGNORECASE,
)
_FAKE_CONFIDENCE = re.compile(
    r"\b\d+(\.\d+)?\s*%\s*(confidence|güven)\b|\b(confidence|güven)\s*(score|skoru)?\s*[:=]?\s*\d+",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

FACTUAL_KINDS = frozenset({"association", "ranking", "quality"})


def validate_claim(claim: Claim, log: EvidenceLog) -> Claim:
    """Return a copy with provenance_ok set. Never invents evidence."""
    reasons: list[str] = []
    if _CAUSAL.search(claim.text):
        reasons.append("causal_language")
    if _FAKE_CONFIDENCE.search(claim.text):
        reasons.append("fake_confidence")
    if claim.kind in FACTUAL_KINDS and not claim.evidence_ids:
        reasons.append("no_evidence")
    missing = [eid for eid in claim.evidence_ids if eid not in log.ids()]
    if missing:
        reasons.append("unknown_evidence_id")
    if claim.kind in FACTUAL_KINDS and claim.evidence_ids:
        payloads = [log.get(eid) for eid in claim.evidence_ids]
        if not _numbers_supported(claim.text, [p.value for p in payloads if p is not None]):
            reasons.append("unbound_number")
    ok = not reasons
    return claim.model_copy(update={"provenance_ok": ok})


def accepted_claims(claims: Iterable[Claim], log: EvidenceLog) -> list[Claim]:
    return [c for c in (validate_claim(c, log) for c in claims) if c.provenance_ok]


def _walk_numbers(value: Any, out: list[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.append(float(value))
        return
    if isinstance(value, str):
        out.extend(float(m) for m in _NUMBER.findall(value))
        return
    if isinstance(value, dict):
        for v in value.values():
            _walk_numbers(v, out)
        return
    if isinstance(value, (list, tuple)):
        for v in value:
            _walk_numbers(v, out)


def _numbers_supported(text: str, values: list[Any], rel: float = 0.005, abs_tol: float = 0.51) -> bool:
    mentioned = [float(m) for m in _NUMBER.findall(text)]
    if not mentioned:
        return True
    pool: list[float] = []
    for value in values:
        _walk_numbers(value, pool)
    for n in mentioned:
        if not any(_close(n, p, rel, abs_tol) for p in pool):
            return False
    return True


def _close(a: float, b: float, rel: float, abs_tol: float) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))
