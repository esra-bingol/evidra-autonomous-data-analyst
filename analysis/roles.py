from __future__ import annotations

import re
from typing import Any

import pandas as pd

ROLES = ("time", "metric", "dimension", "id", "ignore")

_METRIC_TOKENS = {
    "sales": "sales",
    "revenue": "sales",
    "amount": "sales",
    "gmv": "sales",
    "profit": "profit",
    "quantity": "quantity",
    "qty": "quantity",
    "discount": "discount",
    "delay": "delay",
    "score": "review",
    "review": "review",
    "price": "sales",
    "freight": "freight",
    "payment": "sales",
}
_DIM_TOKENS = {
    "region": "region",
    "state": "state",
    "city": "city",
    "category": "product",
    "subcategory": "product",
    "sub_category": "product",
    "segment": "segment",
    "shipmode": "ship_mode",
    "ship_mode": "ship_mode",
}


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def infer_roles(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Infer ColumnRole without hard-coding source spellings."""
    n = len(df)
    roles: list[dict[str, Any]] = []
    for col in df.columns:
        key = normalize_name(col)
        series = df[col]
        nunique = int(series.nunique(dropna=True))
        nullable = bool(series.isna().any())
        role, semantic, dtype = _classify(col, key, series, n, nunique)
        roles.append(
            {
                "name": col,
                "role": role,
                "semantic": semantic,
                "dtype": dtype,
                "nullable": nullable,
            }
        )
    return roles


def _classify(
    col: str, key: str, series: pd.Series, n: int, nunique: int
) -> tuple[str, str, str]:
    if pd.api.types.is_datetime64_any_dtype(series) or "date" in key or "time" in key:
        semantic = "order_date"
        if "ship" in key:
            semantic = "ship_date"
        return "time", semantic, "datetime"

    if pd.api.types.is_numeric_dtype(series):
        for token, semantic in _METRIC_TOKENS.items():
            if token in key:
                return "metric", semantic, str(series.dtype)

    if "category" in key:
        return "dimension", "product", str(series.dtype)

    if key in {"row_id", "rowid"} or key.endswith("_name") or key in {"postal_code", "zip", "zipcode"}:
        return "ignore", key, str(series.dtype)

    if nunique <= 1:
        return "ignore", key, str(series.dtype)

    if key.endswith("_id") or key in {"order_id", "customer_id", "product_id"}:
        semantic = "order" if "order" in key else "customer" if "customer" in key else "product" if "product" in key else "id"
        return "id", semantic, str(series.dtype)

    if pd.api.types.is_numeric_dtype(series):
        if key in {"postal_code", "zip"} or (nunique == n and series.dtype.kind in "iu"):
            return "ignore", key, str(series.dtype)
        if nunique > max(20, n * 0.3):
            return "metric", key, str(series.dtype)

    for token, semantic in _DIM_TOKENS.items():
        if token in key:
            return "dimension", semantic, str(series.dtype)

    if not pd.api.types.is_numeric_dtype(series) and 1 < nunique <= min(200, max(2, n // 2)):
        return "dimension", key, str(series.dtype)

    return "ignore", key, str(series.dtype)


def columns_with_role(roles: list[dict[str, Any]], role: str) -> list[str]:
    return [r["name"] for r in roles if r["role"] == role]


def column_with_semantic(roles: list[dict[str, Any]], semantic: str) -> str | None:
    for r in roles:
        if r["semantic"] == semantic:
            return r["name"]
    return None
