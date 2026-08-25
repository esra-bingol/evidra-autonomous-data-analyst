from __future__ import annotations

from typing import Any

import pandas as pd

from analysis.result import EngineResult
from analysis.roles import column_with_semantic, columns_with_role, infer_roles


def infer_period_windows(time: pd.Series, grain: str | None = None) -> dict[str, Any]:
    """Last complete calendar grain vs the one before. No hard-coded year."""
    s = pd.to_datetime(time, errors="coerce").dropna()
    if s.empty:
        raise ValueError("time column is empty")
    span_days = int((s.max() - s.min()).days)
    grain = grain or ("month" if span_days >= 45 else "week")
    freq = "M" if grain == "month" else "W-MON"
    periods = s.dt.to_period(freq)
    last = periods.max()
    prev = last - 1
    current_start = last.to_timestamp(how="start").normalize()
    current_end = last.to_timestamp(how="end").normalize()
    previous_start = prev.to_timestamp(how="start").normalize()
    previous_end = prev.to_timestamp(how="end").normalize()
    return {
        "grain": grain,
        "previous": {
            "start": previous_start.date().isoformat(),
            "end": previous_end.date().isoformat(),
        },
        "current": {
            "start": current_start.date().isoformat(),
            "end": current_end.date().isoformat(),
        },
    }


def _mask(df: pd.DataFrame, time_col: str, start: str, end: str) -> pd.Series:
    t = pd.to_datetime(df[time_col], errors="coerce")
    return (t >= pd.Timestamp(start)) & (t <= pd.Timestamp(end) + pd.Timedelta(days=0))


def compare_periods(
    df: pd.DataFrame,
    metric: str | None = None,
    time_col: str | None = None,
    windows: dict[str, Any] | None = None,
) -> EngineResult:
    roles = infer_roles(df)
    time_col = time_col or columns_with_role(roles, "time")[0]
    metric = metric or column_with_semantic(roles, "sales") or columns_with_role(roles, "metric")[0]
    windows = windows or infer_period_windows(df[time_col])
    prev_m = _mask(df, time_col, windows["previous"]["start"], windows["previous"]["end"])
    curr_m = _mask(df, time_col, windows["current"]["start"], windows["current"]["end"])
    prev = float(pd.to_numeric(df.loc[prev_m, metric], errors="coerce").sum())
    curr = float(pd.to_numeric(df.loc[curr_m, metric], errors="coerce").sum())
    change = curr - prev
    pct = (100.0 * change / prev) if prev else None
    return EngineResult(
        operation="compare_periods",
        source_columns=[time_col, metric],
        period=windows,
        value={
            "metric": metric,
            "previous": prev,
            "current": curr,
            "change": change,
            "change_pct": None if pct is None else round(pct, 2),
        },
    )


def current_coverage(df: pd.DataFrame, time_col: str | None = None) -> EngineResult:
    """Detect truncated current windows (missingness artefact)."""
    roles = infer_roles(df)
    time_col = time_col or columns_with_role(roles, "time")[0]
    windows = infer_period_windows(df[time_col])
    t = pd.to_datetime(df[time_col], errors="coerce")
    curr_m = _mask(df, time_col, windows["current"]["start"], windows["current"]["end"])
    prev_m = _mask(df, time_col, windows["previous"]["start"], windows["previous"]["end"])
    curr_last = t[curr_m].max()
    period_end = pd.Timestamp(windows["current"]["end"])
    gap_days = None if pd.isna(curr_last) else int((period_end - curr_last.normalize()).days)
    prev_days = t[prev_m].dt.normalize().nunique()
    curr_days = t[curr_m].dt.normalize().nunique()
    truncated = bool(gap_days is not None and gap_days >= 7 and curr_days < prev_days * 0.85)
    return EngineResult(
        operation="current_coverage",
        source_columns=[time_col],
        period=windows,
        value={
            "current_last_observed": None if pd.isna(curr_last) else curr_last.date().isoformat(),
            "gap_days_to_period_end": gap_days,
            "previous_distinct_days": int(prev_days),
            "current_distinct_days": int(curr_days),
            "truncated_current_period": truncated,
        },
    )
