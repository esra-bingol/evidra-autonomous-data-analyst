from __future__ import annotations

from typing import Any

import pandas as pd

from analysis.periods import _mask, infer_period_windows
from analysis.result import EngineResult
from analysis.roles import column_with_semantic, columns_with_role, infer_roles


def decompose_volume_value(
    df: pd.DataFrame,
    metric: str | None = None,
    time_col: str | None = None,
    windows: dict[str, Any] | None = None,
) -> EngineResult:
    roles = infer_roles(df)
    time_col = time_col or columns_with_role(roles, "time")[0]
    metric = metric or column_with_semantic(roles, "sales") or columns_with_role(roles, "metric")[0]
    order_col = column_with_semantic(roles, "order")
    windows = windows or infer_period_windows(df[time_col])

    def stats(mask: pd.Series) -> dict[str, float]:
        part = df.loc[mask]
        sales = float(pd.to_numeric(part[metric], errors="coerce").sum())
        if order_col and order_col in part.columns:
            volume = int(part[order_col].nunique())
        else:
            volume = int(len(part))
        aov = sales / volume if volume else 0.0
        return {"sales": sales, "volume": volume, "aov": aov}

    prev = stats(_mask(df, time_col, windows["previous"]["start"], windows["previous"]["end"]))
    curr = stats(_mask(df, time_col, windows["current"]["start"], windows["current"]["end"]))

    def pct(a: float, b: float) -> float | None:
        return None if not a else round(100.0 * (b - a) / a, 2)

    return EngineResult(
        operation="decompose_volume_value",
        source_columns=[time_col, metric] + ([order_col] if order_col else []),
        period=windows,
        value={
            "previous": prev,
            "current": curr,
            "sales_change_pct": pct(prev["sales"], curr["sales"]),
            "volume_change_pct": pct(float(prev["volume"]), float(curr["volume"])),
            "aov_change_pct": pct(prev["aov"], curr["aov"]),
        },
    )
