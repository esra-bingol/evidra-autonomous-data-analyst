from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Strength = Literal["weak", "moderate", "strong", "inconclusive"]
ClaimKind = Literal["association", "ranking", "quality", "abstention"]


class Evidence(BaseModel):
    """Engine return type. Frozen so a log entry cannot be rewritten in place."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    operation: str
    source_columns: list[str]
    filters: dict[str, Any] = Field(default_factory=dict)
    period: dict[str, Any] | None = None
    value: Any = None
    strength: Strength


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    text: str
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list)
    provenance_ok: bool = False


ReviewDecision = Literal["accept", "reject", "revise", "abstain"]


class ReviewVerdict(BaseModel):
    """Deterministic audit. Does not create evidence."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    decision: ReviewDecision
    reason: str
    issues: list[str] = Field(default_factory=list)
    recommended_strength: Strength | None = None
    recommended_claim: str | None = None


class Chart(BaseModel):
    """Figure is not a source of numbers; it must point at evidence."""

    model_config = ConfigDict(frozen=True)

    kind: str
    plotly: dict[str, Any]
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def _non_empty_ids(cls, ids: list[str]) -> list[str]:
        if not ids or any(not i.strip() for i in ids):
            raise ValueError("charts require evidence_ids")
        return ids
