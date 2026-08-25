from __future__ import annotations

import pandas as pd
from scipy import stats

from analysis.result import EngineResult
from analysis.roles import columns_with_role, infer_roles


def association_test(
    df: pd.DataFrame,
    col_a: str | None = None,
    col_b: str | None = None,
) -> EngineResult:
    """Pearson r and p-value. Does not assert causation."""
    roles = infer_roles(df)
    metrics = columns_with_role(roles, "metric")
    if col_a is None or col_b is None:
        if len(metrics) < 2:
            raise ValueError("need two metric columns")
        col_a, col_b = metrics[0], metrics[1]
    a = pd.to_numeric(df[col_a], errors="coerce")
    b = pd.to_numeric(df[col_b], errors="coerce")
    mask = a.notna() & b.notna()
    aa, bb = a[mask], b[mask]
    if len(aa) < 3 or float(aa.std()) == 0 or float(bb.std()) == 0:
        r, p = float("nan"), float("nan")
    else:
        r, p = stats.pearsonr(aa, bb)
    return EngineResult(
        operation="association_test",
        source_columns=[col_a, col_b],
        value={
            "r": float(r),
            "p_value": float(p),
            "n": int(mask.sum()),
            "interpretation": "association_only",
        },
    )


def summary_statistics(df: pd.DataFrame) -> EngineResult:
    roles = infer_roles(df)
    metrics = columns_with_role(roles, "metric")
    desc = df[metrics].apply(pd.to_numeric, errors="coerce").describe().to_dict()
    return EngineResult(
        operation="summary_statistics",
        source_columns=metrics,
        value=desc,
    )
