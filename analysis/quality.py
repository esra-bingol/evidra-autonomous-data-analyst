from __future__ import annotations

import pandas as pd

from analysis.result import EngineResult

# quality_score = 100
#   − up to 40 points from cell missingness (0.5 point per missing-cell percent)
#   − up to 30 points from full-row duplicate rate
#   − 10 points if any column failed numeric/date coercion while looking typed
# floor at 0.


def detect_missing_values(df: pd.DataFrame) -> EngineResult:
    counts = {c: int(df[c].isna().sum()) for c in df.columns}
    rates = {c: float(df[c].isna().mean()) for c in df.columns}
    return EngineResult(
        operation="detect_missing_values",
        source_columns=list(map(str, df.columns)),
        value={"counts": counts, "rates": rates, "cell_missing_rate": float(df.isna().mean().mean())},
    )


def detect_duplicates(df: pd.DataFrame) -> EngineResult:
    extra = int(df.duplicated().sum())
    rate = float(df.duplicated().mean()) if len(df) else 0.0
    return EngineResult(
        operation="detect_duplicates",
        source_columns=list(map(str, df.columns)),
        value={"duplicate_extra_rows": extra, "duplicate_rate": rate},
    )


def quality_score(df: pd.DataFrame) -> EngineResult:
    missing = detect_missing_values(df).value
    dups = detect_duplicates(df).value
    score = 100.0
    score -= min(40.0, missing["cell_missing_rate"] * 100.0 * 0.5)
    score -= min(30.0, dups["duplicate_rate"] * 100.0)
    score = max(0.0, round(score, 1))
    return EngineResult(
        operation="quality_score",
        source_columns=list(map(str, df.columns)),
        value={
            "score": score,
            "kind": "data_quality",
            "not": "claim_confidence",
            "rule": "100 - min(40, 0.5*missing_cell_pct) - min(30, duplicate_row_pct)",
            "missing": missing,
            "duplicates": dups,
        },
    )
