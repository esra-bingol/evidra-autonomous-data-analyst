"""Generate Phase 1 synthetic fixtures. Seed is fixed; re-run to regenerate CSVs."""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
PREV_START = date(2024, 1, 1)
PREV_END = date(2024, 1, 31)
CURR_START = date(2024, 2, 1)
CURR_END = date(2024, 2, 29)

REGIONS = ("East", "West", "Central", "South")
CATEGORIES = ("Furniture", "Office Supplies", "Technology")
DRIVER_REGION = "West"
DRIVER_CATEGORY = "Office Supplies"

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "fixtures"
FIELDS = [
    "order_id",
    "order_date",
    "region",
    "category",
    "customer_id",
    "sales",
    "quantity",
]


def _dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def _write_csv(name: str, rows: list[dict]) -> None:
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_expected(name: str, payload: dict) -> None:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sales_by_period(rows: list[dict]) -> tuple[float, float]:
    prev = sum(r["sales"] for r in rows if PREV_START <= date.fromisoformat(r["order_date"]) <= PREV_END)
    curr = sum(r["sales"] for r in rows if CURR_START <= date.fromisoformat(r["order_date"]) <= CURR_END)
    return prev, curr


def _orders_by_period(rows: list[dict]) -> tuple[int, int]:
    prev = sum(1 for r in rows if PREV_START <= date.fromisoformat(r["order_date"]) <= PREV_END)
    curr = sum(1 for r in rows if CURR_START <= date.fromisoformat(r["order_date"]) <= CURR_END)
    return prev, curr


def _aov(sales: float, n: int) -> float:
    return sales / n if n else 0.0


def _pct(prev: float, curr: float) -> float:
    return 100.0 * (curr - prev) / prev if prev else 0.0


def _cell_sales(rows: list[dict], region: str, category: str, start: date, end: date) -> float:
    return sum(
        r["sales"]
        for r in rows
        if r["region"] == region
        and r["category"] == category
        and start <= date.fromisoformat(r["order_date"]) <= end
    )


def clear_driver(rng: random.Random) -> list[dict]:
    """West × Office Supplies collapses; other cells stay nearly flat. ~17% total drop."""
    rows: list[dict] = []
    oid = 1
    cid = 1
    prev_days = _dates(PREV_START, PREV_END)
    curr_days = _dates(CURR_START, CURR_END)

    def emit(when: date, region: str, category: str, sales: float) -> None:
        nonlocal oid, cid
        rows.append(
            {
                "order_id": f"CD-{oid:04d}",
                "order_date": when.isoformat(),
                "region": region,
                "category": category,
                "customer_id": f"C-{cid:04d}",
                "sales": round(sales, 2),
                "quantity": 2,
            }
        )
        oid += 1
        cid += 1

    for region in REGIONS:
        for category in CATEGORIES:
            n_prev = 15 if (region, category) == (DRIVER_REGION, DRIVER_CATEGORY) else 5
            for i in range(n_prev):
                emit(prev_days[i * 2 % len(prev_days)], region, category, 200.0)

    for region in REGIONS:
        for category in CATEGORIES:
            n_curr = 15 if (region, category) == (DRIVER_REGION, DRIVER_CATEGORY) else 5
            unit = 40.0 if (region, category) == (DRIVER_REGION, DRIVER_CATEGORY) else 198.0
            for i in range(n_curr):
                jitter = rng.uniform(-1.0, 1.0) if unit == 198.0 else 0.0
                emit(curr_days[i * 2 % len(curr_days)], region, category, unit + jitter)
    return rows


def aov_trap(rng: random.Random) -> list[dict]:
    """Order count almost flat; AOV drops. Calling volume the driver is a fail."""
    rows: list[dict] = []
    oid = 1
    cid = 1
    prev_days = _dates(PREV_START, PREV_END)
    curr_days = _dates(CURR_START, CURR_END)

    def emit(when: date, sales: float, region: str, category: str) -> None:
        nonlocal oid, cid
        rows.append(
            {
                "order_id": f"AT-{oid:04d}",
                "order_date": when.isoformat(),
                "region": region,
                "category": category,
                "customer_id": f"C-{cid:04d}",
                "sales": round(sales, 2),
                "quantity": 1,
            }
        )
        oid += 1
        cid += 1

    n_prev, n_curr = 40, 38
    for i in range(n_prev):
        region = REGIONS[i % 4]
        category = CATEGORIES[i % 3]
        emit(prev_days[i % len(prev_days)], 100.0, region, category)
    for i in range(n_curr):
        region = REGIONS[i % 4]
        category = CATEGORIES[i % 3]
        emit(curr_days[i % len(curr_days)], 70.0 + rng.uniform(-0.5, 0.5), region, category)
    return rows


def no_signal(rng: random.Random) -> list[dict]:
    """Period totals stay in a noise band; no single cell explains a drop."""
    rows: list[dict] = []
    oid = 1
    cid = 1
    prev_days = _dates(PREV_START, PREV_END)
    curr_days = _dates(CURR_START, CURR_END)

    def emit(when: date, region: str, category: str, sales: float) -> None:
        nonlocal oid, cid
        rows.append(
            {
                "order_id": f"NS-{oid:04d}",
                "order_date": when.isoformat(),
                "region": region,
                "category": category,
                "customer_id": f"C-{cid:04d}",
                "sales": round(sales, 2),
                "quantity": 1,
            }
        )
        oid += 1
        cid += 1

    for region in REGIONS:
        for category in CATEGORIES:
            for i in range(4):
                emit(prev_days[(i * 7) % len(prev_days)], region, category, 100.0 + rng.uniform(-2.0, 2.0))
            for i in range(4):
                emit(curr_days[(i * 7) % len(curr_days)], region, category, 100.0 + rng.uniform(-2.0, 2.0))
    return rows


def missingness() -> list[dict]:
    """Current month is truncated (no rows after Feb 18). Daily rate is unchanged."""
    rows: list[dict] = []
    oid = 1
    cid = 1

    def emit(when: date) -> None:
        nonlocal oid, cid
        region = REGIONS[(oid - 1) % 4]
        category = CATEGORIES[(oid - 1) % 3]
        rows.append(
            {
                "order_id": f"MS-{oid:04d}",
                "order_date": when.isoformat(),
                "region": region,
                "category": category,
                "customer_id": f"C-{cid:04d}",
                "sales": 100.0,
                "quantity": 1,
            }
        )
        oid += 1
        cid += 1

    for d in _dates(PREV_START, PREV_END):
        emit(d)
        emit(d)
    cutoff = date(2024, 2, 18)
    for d in _dates(CURR_START, cutoff):
        emit(d)
        emit(d)
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    fixtures = {
        "clear_driver": clear_driver(rng),
        "aov_trap": aov_trap(rng),
        "no_signal": no_signal(rng),
        "missingness": missingness(),
    }

    period = {
        "previous": {"start": PREV_START.isoformat(), "end": PREV_END.isoformat(), "grain": "month"},
        "current": {"start": CURR_START.isoformat(), "end": CURR_END.isoformat(), "grain": "month"},
    }

    for name, rows in fixtures.items():
        _write_csv(f"{name}.csv", rows)
        prev, curr = _sales_by_period(rows)
        n_prev, n_curr = _orders_by_period(rows)
        base = {
            "dataset_id": name,
            "period": period,
            "totals": {
                "sales_previous": round(prev, 2),
                "sales_current": round(curr, 2),
                "sales_change_pct": round(_pct(prev, curr), 2),
                "orders_previous": n_prev,
                "orders_current": n_curr,
                "aov_previous": round(_aov(prev, n_prev), 2),
                "aov_current": round(_aov(curr, n_curr), 2),
                "aov_change_pct": round(_pct(_aov(prev, n_prev), _aov(curr, n_curr)), 2),
            },
        }
        if name == "clear_driver":
            cell_prev = _cell_sales(rows, DRIVER_REGION, DRIVER_CATEGORY, PREV_START, PREV_END)
            cell_curr = _cell_sales(rows, DRIVER_REGION, DRIVER_CATEGORY, CURR_START, CURR_END)
            share = 100.0 * (cell_prev - cell_curr) / (prev - curr) if prev != curr else 0.0
            payload = {
                **base,
                "decision": "primary_driver",
                "primary_driver": f"{DRIVER_REGION} × {DRIVER_CATEGORY}",
                "driver_region": DRIVER_REGION,
                "driver_category": DRIVER_CATEGORY,
                "driver_share_of_drop_pct": round(share, 1),
                "sales_change_pct_band": [-22.0, -12.0],
                "forbidden_claims": ["volume_only_driver", "causal_language", "abstain"],
            }
        elif name == "aov_trap":
            payload = {
                **base,
                "decision": "value_not_volume",
                "primary_driver": "AOV",
                "sales_change_pct_band": [-40.0, -20.0],
                "orders_change_pct_band": [-10.0, 0.0],
                "aov_change_pct_band": [-40.0, -20.0],
                "forbidden_claims": ["order_count_as_primary_driver", "causal_language"],
            }
        elif name == "no_signal":
            payload = {
                **base,
                "decision": "abstain",
                "primary_driver": None,
                "strength": "inconclusive",
                "sales_change_pct_band": [-5.0, 5.0],
                "forbidden_claims": ["named_region_or_category_driver", "causal_language"],
            }
        else:
            payload = {
                **base,
                "decision": "data_artefact",
                "primary_driver": None,
                "artefact": "truncated_current_period",
                "current_last_observed_date": "2024-02-18",
                "forbidden_claims": ["business_segment_driver", "causal_language"],
            }
        _write_expected(f"{name}.expected.json", payload)

    print(f"Wrote {len(fixtures)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
