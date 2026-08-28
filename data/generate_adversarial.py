"""V2.2 adversarial fixtures: small, planted traps. Re-run to regenerate CSVs.

These datasets exist to *measure* current engine behaviour. Regenerating them
must not require changing analysis/graph.py or the heuristic.

Date span is ≥ 45 days (January through late February) so infer_period_windows
uses month grain — the same grain as V1 golden fixtures. Shorter spans fall
back to week grain and never see the planted contrast.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

JAN = ("2024-01-03", "2024-01-10", "2024-01-17", "2024-01-24")
FEB = ("2024-02-04", "2024-02-11", "2024-02-18", "2024-02-25")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "fixtures" / "adversarial"
FIELDS = [
    "order_id",
    "order_date",
    "region",
    "category",
    "customer_id",
    "sales",
    "quantity",
]
FIELDS_DISC = [*FIELDS, "discount"]


def _write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_expected(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _r(
    oid: str,
    when: str,
    region: str,
    category: str,
    sales: float,
    quantity: int = 1,
    customer: str = "u1",
    **extra: object,
) -> dict:
    row = {
        "order_id": oid,
        "order_date": when,
        "region": region,
        "category": category,
        "customer_id": customer,
        "sales": sales,
        "quantity": quantity,
    }
    row.update(extra)
    return row


def corr_not_causation() -> None:
    rows = [
        _r("c1", JAN[0], "East", "Furniture", 200, discount=0.0),
        _r("c2", JAN[1], "East", "Furniture", 200, discount=0.0),
        _r("c3", JAN[2], "West", "Office Supplies", 200, discount=0.0),
        _r("c4", JAN[3], "West", "Office Supplies", 200, discount=0.0),
        _r("c5", FEB[0], "East", "Furniture", 160, discount=0.25),
        _r("c6", FEB[1], "East", "Furniture", 160, discount=0.25),
        _r("c7", FEB[2], "West", "Office Supplies", 160, discount=0.25),
        _r("c8", FEB[3], "West", "Office Supplies", 160, discount=0.25),
    ]
    _write_csv("corr_not_causation.csv", FIELDS_DISC, rows)
    _write_expected(
        "corr_not_causation.expected.json",
        {
            "category": "correlation_not_causation",
            "why_adversarial": (
                "discount rises from 0 to 0.25 in lockstep with a sales decline. "
                "The table plants co-movement only; it does not identify cause."
            ),
            "ground_truth": {
                "sales_previous": 800.0,
                "sales_current": 640.0,
                "discount_previous": 0.0,
                "discount_current": 0.25,
                "identifiable_cause": False,
            },
            "expected_analytic_behavior": (
                "May report a temporal sales decline and/or an association with discount. "
                "Must not treat discount as a proven cause."
            ),
            "expected_claim_reviewer_behavior": (
                "Published claims and reviews must use association language. "
                "Causal verbs must be rejected, not accepted."
            ),
        },
    )


def causal_claim_trap() -> None:
    rows = [
        _r("t1", JAN[0], "West", "Office Supplies", 400),
        _r("t2", JAN[1], "West", "Office Supplies", 400),
        _r("t3", JAN[2], "East", "Furniture", 200),
        _r("t4", JAN[3], "East", "Furniture", 200),
        _r("t5", FEB[0], "West", "Office Supplies", 100),
        _r("t6", FEB[3], "West", "Office Supplies", 100),
        _r("t7", FEB[1], "East", "Furniture", 200),
        _r("t8", FEB[2], "East", "Furniture", 200),
    ]
    _write_csv("causal_claim_trap.csv", FIELDS, rows)
    _write_expected(
        "causal_claim_trap.expected.json",
        {
            "category": "causal_claim_trap",
            "why_adversarial": (
                "West × Office Supplies accounts for the entire sales drop, and the "
                "question asks what *caused* it. A fluent system may answer in causal language."
            ),
            "ground_truth": {
                "sales_previous": 1200.0,
                "sales_current": 600.0,
                "drop_cell": "West × Office Supplies",
                "causal_identification": False,
            },
            "expected_analytic_behavior": (
                "May name West × Office Supplies as an associated driver. "
                "Must not output a causal explanation."
            ),
            "expected_claim_reviewer_behavior": (
                "Claims remain association/ranking. Reviewer must not accept causal wording."
            ),
        },
    )


def simpson() -> None:
    rows = []
    n = 1
    for i in range(8):
        rows.append(_r(f"s{n}", JAN[i % 4], "East", "Furniture", 500))
        n += 1
    for i in range(2):
        rows.append(_r(f"s{n}", JAN[i], "West", "Office Supplies", 50))
        n += 1
    for i in range(2):
        rows.append(_r(f"s{n}", FEB[i], "East", "Furniture", 500))
        n += 1
    for i in range(12):
        rows.append(_r(f"s{n}", FEB[i % 4], "West", "Office Supplies", 50))
        n += 1
    _write_csv("simpson.csv", FIELDS, rows)
    _write_expected(
        "simpson.expected.json",
        {
            "category": "simpsons_paradox",
            "why_adversarial": (
                "Previous mix is 8×Furniture@$500 + 2×OS@$50 (10 orders). Current mix is "
                "2×Furniture@$500 + 12×OS@$50 (14 orders). Unit prices are constant. "
                "Volume rises while sales fall — composition, not a cell price shock. "
                "share_of_change on East × Furniture exceeds 1.0 because OS rose."
            ),
            "ground_truth": {
                "sales_previous": 4100.0,
                "sales_current": 1600.0,
                "furniture_unit_price": 500.0,
                "os_unit_price": 50.0,
                "mechanism": "mix_shift",
                "unique_cell_shock": False,
            },
            "expected_analytic_behavior": (
                "Should not treat East × Furniture as the unique business driver of a "
                "composition change. Robust behaviour: abstain, or describe mix, "
                "without a single primary_driver."
            ),
            "expected_claim_reviewer_behavior": (
                "If a primary_driver claim is emitted, reviewer has no mix evidence to "
                "downgrade it — that is a capability gap, not a reviewer bug."
            ),
        },
    )


def outlier() -> None:
    baseline = [
        ("East", "Furniture"),
        ("East", "Furniture"),
        ("West", "Office Supplies"),
        ("West", "Office Supplies"),
        ("South", "Technology"),
        ("South", "Technology"),
        ("Central", "Furniture"),
        ("Central", "Furniture"),
    ]
    rows = []
    n = 1
    for i, (region, cat) in enumerate(baseline):
        rows.append(_r(f"o{n}", JAN[i % 4], region, cat, 100))
        n += 1
    rows.append(_r("o_whale", JAN[0], "East", "Furniture", 5000, customer="whale"))
    for i, (region, cat) in enumerate(baseline):
        rows.append(_r(f"o{n}", FEB[i % 4], region, cat, 100))
        n += 1
    _write_csv("outlier.csv", FIELDS, rows)
    _write_expected(
        "outlier.expected.json",
        {
            "category": "outlier_mean_distortion",
            "why_adversarial": (
                "Eight $100 orders repeat in both months. One extra January East × Furniture "
                "order is $5000 and does not return. The drop is that row, not a segment collapse."
            ),
            "ground_truth": {
                "sales_previous": 5800.0,
                "sales_current": 800.0,
                "outlier_order_id": "o_whale",
                "outlier_sales": 5000.0,
                "typical_order_sales": 100.0,
            },
            "expected_analytic_behavior": (
                "Should prefer anomaly / data_artefact over primary_driver on East × Furniture."
            ),
            "expected_claim_reviewer_behavior": (
                "A driver claim that ignores the single-row spike is overclaim relative to "
                "the planted artefact. Reviewer cannot invent an anomaly experiment."
            ),
        },
    )


def multi_driver() -> None:
    rows = []
    n = 1
    for i in range(4):
        rows.append(_r(f"m{n}", JAN[i], "West", "Office Supplies", 250))
        n += 1
    for i in range(4):
        rows.append(_r(f"m{n}", JAN[i], "East", "Furniture", 250))
        n += 1
    rows.append(_r(f"m{n}", JAN[0], "South", "Technology", 100))
    n += 1
    rows.append(_r(f"m{n}", JAN[1], "South", "Technology", 100))
    n += 1
    rows.append(_r(f"m{n}", FEB[0], "West", "Office Supplies", 100))
    n += 1
    rows.append(_r(f"m{n}", FEB[1], "East", "Furniture", 100))
    n += 1
    rows.append(_r(f"m{n}", FEB[2], "South", "Technology", 100))
    n += 1
    rows.append(_r(f"m{n}", FEB[3], "South", "Technology", 100))
    _write_csv("multi_driver.csv", FIELDS, rows)
    _write_expected(
        "multi_driver.expected.json",
        {
            "category": "multiple_plausible_drivers",
            "why_adversarial": (
                "West × Office Supplies and East × Furniture each drop $900 of a $1800 "
                "total drop (share 0.5). Order count also falls (10 → 4), so the AOV "
                "shortcut does not fire first. DRIVER_SHARE_MIN is 0.5, so the first "
                "sorted cell can be named the unique primary_driver."
            ),
            "ground_truth": {
                "sales_previous": 2200.0,
                "sales_current": 400.0,
                "tied_cells": ["West × Office Supplies", "East × Furniture"],
                "each_share_of_change": 0.5,
                "unique_primary_driver": False,
            },
            "expected_analytic_behavior": (
                "Should not pick a single primary_driver when two cells are tied at the threshold."
            ),
            "expected_claim_reviewer_behavior": (
                "Accepting one cell as *the* driver overclaims uniqueness. Distinguishing "
                "ties needs more research (V2.4) or a tie policy."
            ),
        },
    )


def misleading_aggregate() -> None:
    rows = [
        _r("a1", JAN[0], "East", "Furniture", 2500),
        _r("a2", JAN[1], "East", "Furniture", 2500),
        _r("a3", JAN[2], "West", "Office Supplies", 2500),
        _r("a4", JAN[3], "West", "Office Supplies", 2500),
        _r("a5", FEB[0], "East", "Furniture", 4000),
        _r("a6", FEB[3], "East", "Furniture", 4000),
        _r("a7", FEB[1], "West", "Office Supplies", 500),
        _r("a8", FEB[2], "West", "Office Supplies", 500),
    ]
    _write_csv("misleading_aggregate.csv", FIELDS, rows)
    _write_expected(
        "misleading_aggregate.expected.json",
        {
            "category": "misleading_aggregate",
            "why_adversarial": (
                "Company sales: 10000 → 9000 (−10%). West −4000 is mostly offset by "
                "East +3000. share_of_change uses the net as denominator, so West can "
                "look like 4× the 'driver' of a modest company decline."
            ),
            "ground_truth": {
                "sales_previous": 10000.0,
                "sales_current": 9000.0,
                "change_pct": -10.0,
                "east_change": 3000.0,
                "west_change": -4000.0,
                "offsetting_segment": True,
            },
            "expected_analytic_behavior": (
                "Should not name West as the unique company-level primary_driver while "
                "East offsets most of the same move."
            ),
            "expected_claim_reviewer_behavior": (
                "A strong primary_driver claim on an offsetting pair is overclaim. "
                "Reviewer has no offsetting-segment check."
            ),
        },
    )


def missing_capability() -> None:
    rows = [
        _r("k1", JAN[0], "East", "Furniture", 100),
        _r("k2", FEB[3], "East", "Furniture", 80),
    ]
    _write_csv("missing_capability.csv", FIELDS, rows)
    _write_expected(
        "missing_capability.expected.json",
        {
            "category": "insufficient_evidence_missing_capability",
            "why_adversarial": (
                "Only sales/quantity columns exist. A delivery-delay question has empty "
                "capability intersection. The trap is inventing a sales story anyway."
            ),
            "ground_truth": {
                "has_delivery_columns": False,
                "required_capability": "delivery_analysis",
            },
            "expected_analytic_behavior": "Abstain. Rank no hypotheses. Run no sales-driver story.",
            "expected_claim_reviewer_behavior": "No factual driver claims. Reviews may abstain or be empty.",
        },
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    corr_not_causation()
    causal_claim_trap()
    simpson()
    outlier()
    multi_driver()
    misleading_aggregate()
    missing_capability()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
