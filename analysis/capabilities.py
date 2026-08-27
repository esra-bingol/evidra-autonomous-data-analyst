from __future__ import annotations

from analysis.result import EngineResult
from analysis.roles import columns_with_role, normalize_name


def _column_keys(names: list[str]) -> set[str]:
    return {normalize_name(n) for n in names}


def detect_capabilities(
    roles: list[dict],
    n_tables: int = 1,
    available_columns: list[str] | None = None,
) -> EngineResult:
    """Flags from schema. causal_analysis stays false. Join/delivery/retention follow columns."""
    times = columns_with_role(roles, "time")
    metrics = columns_with_role(roles, "metric")
    dims = columns_with_role(roles, "dimension")
    ids = columns_with_role(roles, "id")
    names = list(available_columns or [r["name"] for r in roles])
    keys = _column_keys(names)
    delivery = (
        "order_delivered_customer_date" in keys or "order_delivered_customer" in keys
    ) and ("order_purchase_timestamp" in keys or "order_purchase_date" in keys)
    if "delay_days" in keys and "review_score" in keys:
        delivery = True
    retention = any("customer_unique" in k for k in keys)

    flags = {
        "temporal_analysis": bool(times and metrics),
        "segmentation": bool(dims and metrics),
        "metric_comparison": bool(metrics),
        "volume_value_decomposition": bool(metrics and (ids or True)),
        "interaction": bool(len(dims) >= 2 and metrics),
        "anomaly_detection": bool(metrics),
        "association": bool(len(metrics) >= 2 or (metrics and dims)),
        "causal_analysis": False,
        "multi_table_join": n_tables >= 2,
        "delivery_analysis": bool(delivery),
        "retention_analysis": bool(retention),
    }
    return EngineResult(
        operation="detect_capabilities",
        source_columns=[r["name"] for r in roles],
        value=flags,
    )
