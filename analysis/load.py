from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from analysis.olist import SourceBundle, assemble_investigation_frame, is_olist_dir, load_olist_tables

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


def load_source(path: str | Path) -> SourceBundle:
    """Single table, Olist directory, or zip of Olist CSVs. Geolocation is not loaded."""
    path = Path(path)
    if path.is_dir() and is_olist_dir(path):
        tables = load_olist_tables(path)
        df, assemble = assemble_investigation_frame(tables)
        df = _coerce_datetimes(df)
        return SourceBundle(
            df=df,
            tables=tables,
            meta={
                "kind": "olist",
                "n_tables": len(tables),
                "assemble": assemble.to_dict(),
            },
        )
    if path.suffix.lower() == ".zip":
        dest = path.parent / f"{path.stem}_extracted"
        dest.mkdir(parents=True, exist_ok=True)
        with ZipFile(path) as zf:
            for info in zf.infolist():
                name = Path(info.filename).name
                if not name.lower().endswith(".csv"):
                    continue
                if ".." in Path(info.filename).parts:
                    raise ValueError("zip path traversal")
                target = dest / name
                target.write_bytes(zf.read(info))
        return load_source(dest)
    df = load_tabular(path)
    return SourceBundle(df=df, tables={}, meta={"kind": "single", "n_tables": 1})


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
