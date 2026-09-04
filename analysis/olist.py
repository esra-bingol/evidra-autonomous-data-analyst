from __future__ import annotations

import duckdb
import pandas as pd

from analysis.result import EngineResult
from analysis.source import SourceBundle

OLIST_TABLES = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_customers_dataset.csv": "customers",
    "olist_products_dataset.csv": "products",
    "olist_order_payments_dataset.csv": "payments",
    "olist_order_reviews_dataset.csv": "reviews",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}
SKIP_FILES = frozenset({"olist_geolocation_dataset.csv", "superstore.csv"})
JOIN_KEYS = ("order_id", "customer_id", "product_id", "seller_id")
REQUIRED_OLIST = ("olist_orders_dataset.csv", "olist_order_items_dataset.csv", "olist_order_reviews_dataset.csv")

ASSEMBLE_SQL = """
SELECT
  o.order_id,
  c.customer_unique_id,
  c.customer_state,
  o.order_purchase_timestamp,
  date_diff(
    'day',
    CAST(o.order_purchase_timestamp AS TIMESTAMP),
    CAST(o.order_delivered_customer_date AS TIMESTAMP)
  ) AS delay_days,
  r.review_score,
  agg.gmv,
  agg.product_category_name_english
FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
INNER JOIN (
  SELECT
    i.order_id,
    SUM(i.price) AS gmv,
    MIN(COALESCE(t.product_category_name_english, p.product_category_name)) AS product_category_name_english
  FROM order_items i
  INNER JOIN products p ON i.product_id = p.product_id
  LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name
  GROUP BY i.order_id
) agg ON o.order_id = agg.order_id
INNER JOIN (
  SELECT order_id, AVG(CAST(review_score AS DOUBLE)) AS review_score
  FROM reviews
  GROUP BY order_id
) r ON o.order_id = r.order_id
WHERE o.order_delivered_customer_date IS NOT NULL
  AND o.order_purchase_timestamp IS NOT NULL
"""

CATEGORY_SQL = """
SELECT
  product_category_name_english AS category,
  AVG(review_score) AS avg_review,
  SUM(gmv) AS gmv,
  COUNT(*) AS n_orders
FROM df
GROUP BY 1
HAVING COUNT(*) >= 30
ORDER BY gmv DESC
"""


def is_olist_dir(path) -> bool:
    from pathlib import Path

    root = Path(path)
    return root.is_dir() and (root / "olist_orders_dataset.csv").exists()


def olist_available(path) -> bool:
    from pathlib import Path

    root = Path(path)
    return all((root / name).exists() for name in REQUIRED_OLIST)


def load_olist_tables(root) -> dict[str, pd.DataFrame]:
    from pathlib import Path

    from analysis.load import load_tabular

    root = Path(root)
    tables: dict[str, pd.DataFrame] = {}
    for filename, alias in OLIST_TABLES.items():
        path = root / filename
        if path.exists():
            tables[alias] = load_tabular(path)
    missing = [alias for alias in ("orders", "order_items", "customers", "products", "reviews") if alias not in tables]
    if missing:
        raise FileNotFoundError(f"Olist tables missing: {missing}")
    return tables


def assemble_investigation_frame(tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, EngineResult]:
    con = duckdb.connect(database=":memory:")
    try:
        for name, frame in tables.items():
            con.register(name, frame)
        df = con.execute(ASSEMBLE_SQL).fetchdf()
    finally:
        con.close()
    used = [
        "orders",
        "customers",
        "order_items",
        "products",
        "category_translation",
        "reviews",
    ]
    result = EngineResult(
        operation="join_assemble",
        source_columns=["order_id", "delay_days", "review_score", "gmv", "product_category_name_english"],
        filters={"sql": "join_assemble", "tables": [t for t in used if t in tables]},
        value={
            "tables": [t for t in used if t in tables],
            "join_keys": list(JOIN_KEYS),
            "delay_column": "delay_days",
            "n": int(len(df)),
            "derived_in_engine": True,
        },
    )
    return df, result
