from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, Field

StopReason = Literal["strong_evidence", "space_exhausted", "budget", "abstain"]
TemplateId = Literal[
    "temporal_change",
    "volume_vs_value",
    "segment_driver",
    "interaction",
    "association",
    "data_artefact",
    "anomaly",
]

CLOSED_TEMPLATES: frozenset[str] = frozenset(get_args(TemplateId))

V1_TOOLS = (
    "inspect_dataset",
    "profile_dataset",
    "detect_capabilities",
    "compare_periods",
    "segment_by",
    "decompose_volume_value",
    "test_hypothesis",
    "detect_anomalies",
    "statistical_test",
    "create_chart",
    "run_sql",
    "generate_report",
)


class Budget(BaseModel):
    max_hypotheses: int = 8
    max_experiments: int = 20
    max_interaction_depth: int = 2
    max_seconds: float = 60.0
    hypotheses_used: int = 0
    experiments_used: int = 0
    started_monotonic: float = 0.0


class Trace(BaseModel):
    tool: str
    duration_ms: float
    ok: bool
    summary: str
    error: str | None = None


class Hypothesis(BaseModel):
    hypothesis_id: str
    template_id: TemplateId
    bindings: dict[str, Any] = Field(default_factory=dict)
    status: Literal["ranked", "bound", "skipped", "tested", "dropped"] = "ranked"
    selected_by: Literal["heuristic"] = "heuristic"


class ToolError(BaseModel):
    ok: Literal[False] = False
    error: str
    evidence_ids: list[str] = Field(default_factory=list)


class ToolOk(BaseModel):
    ok: Literal[True] = True
    evidence_ids: list[str]
    summary: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)
