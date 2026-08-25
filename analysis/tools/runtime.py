from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from analysis.anomalies import detect_anomalies
from analysis.capabilities import detect_capabilities
from analysis.evidence.log import EvidenceLog
from analysis.evidence.models import Chart
from analysis.periods import compare_periods, current_coverage
from analysis.profiler import profile_dataset
from analysis.quality import quality_score
from analysis.result import EngineResult
from analysis.roles import column_with_semantic, columns_with_role, infer_roles
from analysis.segments import segment_by
from analysis.statistics import association_test
from analysis.tools.schemas import (
    CLOSED_TEMPLATES,
    Budget,
    Hypothesis,
    ToolError,
    ToolOk,
    Trace,
)
from analysis.tools.sql import run_sql
from analysis.visualization import create_visualization
from analysis.volume_value import decompose_volume_value


@dataclass
class ToolContext:
    df: pd.DataFrame
    log: EvidenceLog
    traces: list[Trace] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    charts: list[Chart] = field(default_factory=list)


def inspect_dataset(df: pd.DataFrame) -> EngineResult:
    sample = df.head(5)
    return EngineResult(
        operation="inspect_dataset",
        source_columns=list(map(str, df.columns)),
        value={
            "n_rows": int(len(df)),
            "n_cols": int(df.shape[1]),
            "columns": list(map(str, df.columns)),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "sample": sample.astype(object).where(sample.notna(), None).to_dict(orient="records"),
        },
    )


def _guard_frame(df: pd.DataFrame) -> None:
    if df is None or df.shape[1] == 0:
        raise ValueError("empty column set")
    if len(df) == 0:
        raise ValueError("empty column / empty table")


def _require_time(df: pd.DataFrame) -> str:
    roles = infer_roles(df)
    times = columns_with_role(roles, "time")
    if not times:
        raise ValueError("missing date/time column")
    series = pd.to_datetime(df[times[0]], errors="coerce")
    if series.notna().sum() == 0:
        raise ValueError("missing date/time column")
    if series.dropna().dt.to_period("M").nunique() < 2:
        raise ValueError("single period only; need two periods to compare")
    return times[0]


def call_tool(ctx: ToolContext, name: str, **kwargs: Any) -> ToolOk | ToolError:
    started = time.monotonic()
    try:
        evidence_ids, extra = _dispatch(ctx, name, **kwargs)
        extra = {k: v for k, v in extra.items() if not isinstance(v, pd.DataFrame)}
        summary = extra.pop("summary", name)
        duration = (time.monotonic() - started) * 1000
        ctx.traces.append(
            Trace(tool=name, duration_ms=round(duration, 2), ok=True, summary=summary)
        )
        return ToolOk(evidence_ids=evidence_ids, summary=summary, extra=extra)
    except Exception as exc:
        duration = (time.monotonic() - started) * 1000
        msg = str(exc)
        ctx.traces.append(
            Trace(tool=name, duration_ms=round(duration, 2), ok=False, summary=name, error=msg)
        )
        return ToolError(error=msg)


def _append(ctx: ToolContext, result: EngineResult) -> str:
    return ctx.log.append_result(result).evidence_id


def _dispatch(ctx: ToolContext, name: str, **kwargs: Any) -> tuple[list[str], dict[str, Any]]:
    _guard_frame(ctx.df)
    df = ctx.df
    if name == "inspect_dataset":
        eid = _append(ctx, inspect_dataset(df))
        return [eid], {"summary": "inspect"}
    if name == "profile_dataset":
        profile = profile_dataset(df)
        quality = quality_score(df)
        return [_append(ctx, profile), _append(ctx, quality)], {"summary": "profile+quality"}
    if name == "detect_capabilities":
        roles = infer_roles(df)
        eid = _append(ctx, detect_capabilities(roles))
        return [eid], {"summary": "capabilities", "roles": roles}
    if name == "compare_periods":
        _require_time(df)
        eid = _append(ctx, compare_periods(df))
        return [eid], {"summary": "compare_periods"}
    if name == "segment_by":
        dims = list(kwargs.get("dimensions") or [])
        if not dims:
            raise ValueError("empty column: segment_by needs dimensions")
        missing = [d for d in dims if d not in df.columns]
        if missing:
            raise ValueError(f"empty column: {missing[0]} not in dataset")
        _require_time(df)
        eid = _append(ctx, segment_by(df, dims))
        return [eid], {"summary": f"segment_by {dims}"}
    if name == "decompose_volume_value":
        _require_time(df)
        eid = _append(ctx, decompose_volume_value(df))
        return [eid], {"summary": "volume_value"}
    if name == "detect_anomalies":
        eid = _append(ctx, detect_anomalies(df))
        return [eid], {"summary": "anomalies"}
    if name == "statistical_test":
        eid = _append(ctx, association_test(df, kwargs.get("col_a"), kwargs.get("col_b")))
        return [eid], {"summary": "statistical_test"}
    if name == "run_sql":
        eid = _append(ctx, run_sql(df, str(kwargs.get("sql") or "")))
        return [eid], {"summary": "run_sql"}
    if name == "create_chart":
        kind = str(kwargs.get("kind") or "trend")
        raw = create_visualization(df, kind=kind)
        ids = list(ctx.log.ids())
        if not ids:
            raise ValueError("create_chart requires prior evidence")
        chart = Chart(
            kind=kind,
            plotly=(raw.value or {}).get("plotly") or {},
            evidence_ids=ids[-3:],
        )
        ctx.charts.append(chart)
        eid = _append(ctx, raw)
        return [eid], {"summary": f"chart:{kind}"}
    if name == "test_hypothesis":
        hyp: Hypothesis = kwargs["hypothesis"]
        return _test_hypothesis(ctx, hyp)
    if name == "generate_report":
        return [], {"summary": "generate_report"}
    raise ValueError(f"unknown tool {name}")


def _test_hypothesis(ctx: ToolContext, hyp: Hypothesis) -> tuple[list[str], dict[str, Any]]:
    tmpl = hyp.template_id
    if tmpl not in CLOSED_TEMPLATES:
        raise ValueError(f"unknown template_id {tmpl}")
    binds = hyp.bindings
    if tmpl == "temporal_change":
        return _dispatch(ctx, "compare_periods")
    if tmpl == "volume_vs_value":
        return _dispatch(ctx, "decompose_volume_value")
    if tmpl == "segment_driver":
        dim = binds.get("dimension")
        return _dispatch(ctx, "segment_by", dimensions=[dim] if dim else [])
    if tmpl == "interaction":
        dims = binds.get("dimensions") or []
        if len(dims) > ctx.budget.max_interaction_depth:
            raise ValueError("interaction depth exceeds budget")
        return _dispatch(ctx, "segment_by", dimensions=dims)
    if tmpl == "association":
        return _dispatch(ctx, "statistical_test")
    if tmpl == "data_artefact":
        _require_time(df := ctx.df)
        eids = [_append(ctx, quality_score(df)), _append(ctx, current_coverage(df))]
        return eids, {"summary": "data_artefact"}
    if tmpl == "anomaly":
        return _dispatch(ctx, "detect_anomalies")
    raise ValueError(f"unknown template_id {tmpl}")
