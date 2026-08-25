from __future__ import annotations

from pathlib import Path

import pandas as pd

_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


def load_tabular(path: str | Path) -> pd.DataFrame:
    """Load CSV or Excel. Superstore and synthetic fixtures share this API."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif suffix in {".csv", ".txt"}:
        df = _read_csv(path)
    else:
        df = _read_csv(path)
    return _coerce_datetimes(df)


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for enc in _ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error or UnicodeDecodeError("utf-8", b"", 0, 1, "unable to decode")


def _coerce_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            continue
        key = str(col).lower()
        if "date" not in key and "time" not in key:
            continue
        parsed = pd.to_datetime(out[col], errors="coerce")
        if parsed.notna().mean() >= 0.8:
            out[col] = parsed
    return out
