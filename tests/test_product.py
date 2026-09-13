from __future__ import annotations

import json
from pathlib import Path

from analysis.eval.product import run_product
from analysis.roles import infer_roles
from analysis.load import load_tabular

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "fixtures" / "taxi_trips.csv"


def test_taxi_roles_are_schema_tokens_not_a_new_tool():
    df = load_tabular(FIXTURE)
    roles = {r["name"]: r for r in infer_roles(df)}
    assert roles["pickup_datetime"]["role"] == "time"
    assert roles["fare_amount"]["semantic"] == "sales"
    assert roles["pickup_borough"]["semantic"] == "region"
    assert roles["passenger_count"]["semantic"] == "quantity"


def test_product_catalog_covers_three_sources():
    catalog = json.loads((ROOT / "evals" / "product.json").read_text(encoding="utf-8"))
    datasets = {i["dataset"] for i in catalog["items"]}
    assert {"taxi_trips", "superstore", "olist"} <= datasets


def test_product_taxi_questions_pass():
    report = run_product(include_optional=False)
    taxi = [r for r in report["items"] if r.get("dataset") == "taxi_trips"]
    failed = [r for r in taxi if not r["pass"]]
    assert taxi and report["n_scored"] >= 3
    assert not failed, failed
    assert report["pass"]
