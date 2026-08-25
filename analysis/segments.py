from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from analysis.periods import _mask, compare_periods, infer_period_windows
from analysis.result import EngineResult
from analysis.roles import column_with_semantic, columns_with_role, infer_roles


def segment_by(
    df: pd.DataFrame,
    dimensions: Sequence[str],
    metric: str | None = None,
    time_col: str | None = None,
    windows: dict[str, Any] | None = None,
) -> EngineResult:
    roles = infer_roles(df)
    time_col = time_col or columns_with_role(roles, "time")[0]
    metric = metric or column_with_semantic(roles, "sales") or columns_with_role(roles, "metric")[0]
    dims = list(dimensions)
    windows = windows or infer_period_windows(df[time_col])
    totals = compare_periods(df, metric=metric, time_col=time_col, windows=windows).value
    overall_change = totals["change"]

    def agg(start: str, end: str) -> pd.Series:
        mask = _mask(df, time_col, start, end)
        chunk = df.loc[mask, [*dims, metric]].copy()
        chunk[metric] = pd.to_numeric(chunk[metric], errors="coerce")
        return chunk.groupby(dims, dropna=False)[metric].sum()

    prev = agg(windows["previous"]["start"], windows["previous"]["end"])
    curr = agg(windows["current"]["start"], windows["current"]["end"])
    table = pd.concat({"previous": prev, "current": curr}, axis=1).fillna(0.0)
    table["change"] = table["current"] - table["previous"]
    table["share_of_change"] = table["change"] / overall_change if overall_change else 0.0
    table = table.sort_values("change", ascending=True).reset_index()

    records = []
    for _, row in table.iterrows():
        rec = {d: row[d] for d in dims}
        rec["previous"] = float(row["previous"])
        rec["current"] = float(row["current"])
        rec["change"] = float(row["change"])
        rec["share_of_change"] = float(row["share_of_change"])
        records.append(rec)

    return EngineResult(
        operation="segment_by",
        source_columns=[time_col, metric, *dims],
        period=windows,
        filters={"dimensions": dims},
        value={"metric": metric, "rows": records, "overall": totals},
    )
