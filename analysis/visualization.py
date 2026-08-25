from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from analysis.periods import compare_periods, infer_period_windows
from analysis.result import EngineResult
from analysis.roles import column_with_semantic, columns_with_role, infer_roles
from analysis.segments import segment_by


def create_visualization(
    df: pd.DataFrame,
    kind: str = "trend",
    dimension: str | None = None,
) -> EngineResult:
    roles = infer_roles(df)
    time_col = columns_with_role(roles, "time")[0]
    metric = column_with_semantic(roles, "sales") or columns_with_role(roles, "metric")[0]
    t = pd.to_datetime(df[time_col], errors="coerce")
    y = pd.to_numeric(df[metric], errors="coerce")

    if kind == "trend":
        g = pd.DataFrame({"t": t, "y": y}).dropna()
        g = g.set_index("t").resample("ME")["y"].sum()
        fig = go.Figure(go.Scatter(x=list(g.index.astype(str)), y=list(g.values), mode="lines+markers"))
        fig.update_layout(title=f"{metric} over time", xaxis_title="period", yaxis_title=metric)
        source = [time_col, metric]
        filters: dict[str, Any] = {"kind": "trend"}
    else:
        dim = dimension or next(
            (c for c in columns_with_role(roles, "dimension") if "region" in c.lower()),
            columns_with_role(roles, "dimension")[0],
        )
        windows = infer_period_windows(df[time_col])
        seg = segment_by(df, [dim], metric=metric, time_col=time_col, windows=windows)
        rows = seg.value["rows"][:12]
        fig = go.Figure(
            go.Bar(
                x=[str(r[dim]) for r in rows],
                y=[r["change"] for r in rows],
            )
        )
        fig.update_layout(title=f"{metric} change by {dim}", xaxis_title=dim, yaxis_title="change")
        source = [time_col, metric, dim]
        filters = {"kind": "segment_change", "dimension": dim}

    _ = compare_periods  # period context available to callers
    return EngineResult(
        operation="create_visualization",
        source_columns=source,
        filters=filters,
        value={"plotly": fig.to_plotly_json(), "kind": filters["kind"]},
    )
