from __future__ import annotations

import pandas as pd

from analysis.result import EngineResult
from analysis.roles import column_with_semantic, columns_with_role, infer_roles


def detect_anomalies(df: pd.DataFrame, metric: str | None = None) -> EngineResult:
    """IQR on the metric; monthly z-score if a time column exists. No ML."""
    roles = infer_roles(df)
    metric = metric or column_with_semantic(roles, "sales") or columns_with_role(roles, "metric")[0]
    x = pd.to_numeric(df[metric], errors="coerce")
    q1, q3 = x.quantile(0.25), x.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    iqr_flags = (x < low) | (x > high)

    time_cols = columns_with_role(roles, "time")
    monthly: list[dict] = []
    if time_cols:
        t = pd.to_datetime(df[time_cols[0]], errors="coerce")
        g = pd.DataFrame({"t": t, "x": x}).dropna().set_index("t").resample("ME")["x"].sum()
        if len(g) >= 3 and g.std(ddof=0) > 0:
            z = (g - g.mean()) / g.std(ddof=0)
            for ts, zv in z.items():
                if abs(float(zv)) >= 2.5:
                    monthly.append({"period": ts.date().isoformat(), "z": round(float(zv), 2)})

    return EngineResult(
        operation="detect_anomalies",
        source_columns=[metric] + time_cols[:1],
        value={
            "metric": metric,
            "iqr_bounds": {"low": float(low), "high": float(high)},
            "iqr_outlier_rows": int(iqr_flags.fillna(False).sum()),
            "monthly_z_outliers": monthly,
        },
    )
