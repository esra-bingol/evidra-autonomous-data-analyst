"""Invoice line-item canonicalization (UCI Online Retail II and same-schema files).

Maps raw retail columns onto the existing role table. Does not add analysis tools.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.result import EngineResult
from analysis.roles import normalize_name
from analysis.source import SourceBundle

_INVOICE = frozenset({"invoice", "invoiceno", "invoice_no", "invoice_number"})
_STOCK = frozenset({"stockcode", "stock_code", "sku", "stock"})
_QTY = frozenset({"quantity", "qty"})
_PRICE = frozenset({"price", "unitprice", "unit_price"})
_VALUE = frozenset({"amount", "sales", "revenue", "gmv", "line_amount"})


def _keys(columns) -> set[str]:
    return {normalize_name(c) for c in columns}


def looks_like_retail_line_item(df: pd.DataFrame) -> bool:
    keys = _keys(df.columns)
    has_time = any("date" in k or "time" in k for k in keys)
    has_invoice = bool(keys & _INVOICE) or any(k.startswith("invoice") and "date" not in k for k in keys)
    return bool((keys & _QTY) and (keys & _STOCK) and (keys & _PRICE) and has_time and has_invoice)


def canonicalize_retail_line_item(df: pd.DataFrame) -> tuple[pd.DataFrame, EngineResult]:
    """Raw invoice rows → investigation frame. Quantity × unit price becomes `amount` when missing."""
    out = df.copy()
    key_to_col = {normalize_name(c): c for c in out.columns}
    qty_col = next(key_to_col[k] for k in key_to_col if k in _QTY)
    price_col = next(key_to_col[k] for k in key_to_col if k in _PRICE)
    invoice_col = next(
        (key_to_col[k] for k in key_to_col if k in _INVOICE or (k.startswith("invoice") and "date" not in k)),
        None,
    )

    derived: list[str] = []
    if not (set(key_to_col) & _VALUE):
        qty = pd.to_numeric(out[qty_col], errors="coerce")
        price = pd.to_numeric(out[price_col], errors="coerce")
        out["amount"] = qty * price
        derived.append("amount")

    if normalize_name(price_col) in {"price", "unitprice"} and price_col in out.columns:
        out = out.rename(columns={price_col: "unit_price"})

    dropped = 0
    if invoice_col is not None:
        inv = out[invoice_col].astype(str)
        cancel_inv = inv.str.upper().str.startswith("C")
    else:
        cancel_inv = pd.Series(False, index=out.index)
    qty = pd.to_numeric(out[qty_col], errors="coerce")
    cancel = cancel_inv | (qty < 0)
    dropped = int(cancel.fillna(False).sum())
    out = out.loc[~cancel.fillna(False)].copy()
    if "amount" in out.columns:
        out = out.loc[out["amount"].notna()].copy()

    result = EngineResult(
        operation="canonicalize",
        source_columns=list(map(str, df.columns)),
        filters={"kind": "retail_line_item"},
        value={
            "kind": "retail_line_item",
            "derived_columns": derived,
            "dropped_cancelled_or_negative": dropped,
            "n": int(len(out)),
            "derived_in_adapter": True,
        },
    )
    return out, result


def load_retail_workbook(path: Path) -> pd.DataFrame | None:
    if path.suffix.lower() not in {".xlsx", ".xls"}:
        return None
    sheets = pd.read_excel(path, sheet_name=None)
    frames = [frame for frame in sheets.values() if looks_like_retail_line_item(frame)]
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def try_load_retail(path: Path) -> SourceBundle | None:
    path = Path(path)
    if not path.is_file():
        return None
    raw = None
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = load_retail_workbook(path)
    if raw is None:
        from analysis.load import load_tabular

        raw = load_tabular(path)
        if not looks_like_retail_line_item(raw):
            return None
    if not looks_like_retail_line_item(raw):
        return None
    df, assemble = canonicalize_retail_line_item(raw)
    return SourceBundle(
        df=df,
        tables={},
        meta={
            "kind": "retail_line_item",
            "n_tables": 1,
            "assemble": assemble.to_dict(),
        },
    )
