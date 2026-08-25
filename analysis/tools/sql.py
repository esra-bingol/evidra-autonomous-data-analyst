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


def run_sql(df: pd.DataFrame, sql: str) -> EngineResult:
    """DuckDB SELECT only against a single registered table named df."""
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
