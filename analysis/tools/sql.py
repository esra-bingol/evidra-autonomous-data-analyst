from __future__ import annotations

import re

import duckdb
import pandas as pd

from analysis.result import EngineResult

_WRITE = re.compile(
    r"\b(insert|update|delete|drop|alter|copy|attach|create|export|install|pragma|replace|merge|truncate|grant)\b",
    re.IGNORECASE,
)
ROW_LIMIT = 200


def run_sql(df: pd.DataFrame, sql: str, tables: dict[str, pd.DataFrame] | None = None) -> EngineResult:
    """DuckDB SELECT only. Registers `df` plus optional named catalog tables."""
    text = sql.strip().rstrip(";")
    if not text:
        raise ValueError("empty SQL")
    if ";" in text:
        raise ValueError("run_sql allows a single SELECT only")
    head = text.lstrip().split(None, 1)[0].lower()
    if head not in {"select", "with"}:
        raise ValueError("run_sql allows SELECT only")
    if _WRITE.search(text):
        raise ValueError("run_sql forbids non-SELECT statements")
    con = duckdb.connect(database=":memory:")
    try:
        con.register("df", df)
        for name, frame in (tables or {}).items():
            if re.fullmatch(r"[a-z_][a-z0-9_]*", name):
                con.register(name, frame)
        limited = f"SELECT * FROM ({text}) AS _evidra_q LIMIT {ROW_LIMIT}"
        out = con.execute(limited).fetchdf()
    finally:
        con.close()
    records = out.astype(object).where(out.notna(), None).to_dict(orient="records")
    return EngineResult(
        operation="run_sql",
        source_columns=list(map(str, out.columns)),
        filters={"sql": text, "row_limit": ROW_LIMIT},
        value={"rows": records, "n": int(len(records))},
    )
