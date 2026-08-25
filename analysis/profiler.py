from __future__ import annotations

from typing import Any

import pandas as pd

from analysis.result import EngineResult
from analysis.roles import infer_roles


def profile_dataset(df: pd.DataFrame) -> EngineResult:
    roles = infer_roles(df)
    sample = df.head(5)
    value: dict[str, Any] = {
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "columns": list(map(str, df.columns)),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "roles": roles,
        "sample": sample.astype(object).where(sample.notna(), None).to_dict(orient="records"),
    }
    return EngineResult(
        operation="profile_dataset",
        source_columns=list(map(str, df.columns)),
        value=value,
    )
