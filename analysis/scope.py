"""Slice filters for follow-up investigations. Does not add operators."""

from __future__ import annotations

from typing import Any

import pandas as pd


def atomic_labels(labels: list[str]) -> list[str]:
    out: list[str] = []
    for lab in labels:
        if any(sep in lab for sep in ("×", " x ", " X ")):
            continue
        text = lab.strip()
        if text and text not in out:
            out.append(text)
    return out


def resolve_scope(run: dict[str, Any] | None, labels: list[str]) -> dict[str, str]:
    """Map mentioned labels to dimension columns from frozen segment evidence."""
    if not run or not labels:
        return {}
    wanted = {lab.lower(): lab for lab in atomic_labels(labels)}
    if not wanted:
        return {}
    scope: dict[str, str] = {}
    for ev in run.get("evidence") or []:
        if ev.get("operation") != "segment_by":
            continue
        dims = list((ev.get("filters") or {}).get("dimensions") or [])
        for row in (ev.get("value") or {}).get("rows") or []:
            keys = dims or [k for k in row if k not in {"previous", "current", "change", "share_of_change"}]
            for dim in keys:
                val = row.get(dim)
                if val is None:
                    continue
                hit = wanted.get(str(val).lower())
                if hit is not None:
                    scope[str(dim)] = str(val)
    return scope


def apply_scope(df: pd.DataFrame, scope: dict[str, str]) -> pd.DataFrame:
    if df is None or not scope:
        return df
    out = df
    for col, val in scope.items():
        match = _column(out, col)
        if match is None:
            raise ValueError(f"unknown scope column: {col}")
        out = out.loc[out[match].astype(str) == str(val)]
    return out


def _column(df: pd.DataFrame, name: str) -> str | None:
    if name in df.columns:
        return name
    target = name.strip().lower()
    for col in df.columns:
        if str(col).strip().lower() == target:
            return str(col)
    return None


def scope_lead(scope: dict[str, str]) -> str:
    values = [str(v) for v in scope.values() if v]
    if not values:
        return "Bu dilimi ayrı bir hipotez olarak inceliyorum."
    if len(values) == 1:
        return f"{values[0]}'i ayrı bir hipotez olarak inceliyorum."
    return f"{values[0]} bölgesindeki {values[1]} dilimini ayrı bir hipotez olarak inceliyorum."
