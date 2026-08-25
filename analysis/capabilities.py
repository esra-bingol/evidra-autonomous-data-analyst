from __future__ import annotations

from analysis.result import EngineResult
from analysis.roles import columns_with_role


def detect_capabilities(
    roles: list[dict],
    n_tables: int = 1,
) -> EngineResult:
    """Flags from the role table. causal / join / delivery / retention are false in V1."""
    times = columns_with_role(roles, "time")
    metrics = columns_with_role(roles, "metric")
    dims = columns_with_role(roles, "dimension")
    ids = columns_with_role(roles, "id")
    numeric_or_metric = metrics  # association: ≥2 numeric via metrics

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
        "delivery_analysis": False,
        "retention_analysis": False,
    }
    return EngineResult(
        operation="detect_capabilities",
        source_columns=[r["name"] for r in roles],
        value=flags,
    )
