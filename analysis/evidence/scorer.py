"""Rule-based strength. Not claim confidence; not an LLM label.

- |change| in the noise band → inconclusive
- large period move without a concentrated cell → moderate
- one cell accounts for most of the change (share ≥ 0.8) → strong
- share in [0.5, 0.8) → moderate; below 0.5 → weak
- AOV move large and volume nearly flat → strong on volume_value
- truncated window / quality profile → artefact evidence is strong or inconclusive
"""

from __future__ import annotations

from typing import Any

from analysis.evidence.models import Strength

NOISE_PCT = 5.0


def score_operation(operation: str, value: Any) -> Strength:
    if operation == "compare_periods":
        pct = abs((value or {}).get("change_pct") or 0)
        if pct <= NOISE_PCT:
            return "inconclusive"
        if pct >= 15:
            return "strong"
        if pct >= 8:
            return "moderate"
        return "weak"
    if operation == "segment_by":
        rows = (value or {}).get("rows") or []
        if not rows:
            return "inconclusive"
        share = abs(rows[0].get("share_of_change") or 0)
        if share >= 0.8:
            return "strong"
        if share >= 0.5:
            return "moderate"
        return "weak"
    if operation == "decompose_volume_value":
        aov = abs((value or {}).get("aov_change_pct") or 0)
        vol = abs((value or {}).get("volume_change_pct") or 0)
        if aov >= 20 and vol <= 10 and aov > vol:
            return "strong"
        if aov > vol:
            return "moderate"
        return "weak"
    if operation == "current_coverage":
        return "strong" if (value or {}).get("truncated_current_period") else "inconclusive"
    if operation in {"quality_score", "detect_missing_values", "detect_duplicates"}:
        return "inconclusive"
    if operation == "detect_capabilities":
        return "inconclusive"
    if operation == "profile_dataset":
        return "inconclusive"
    if operation == "create_visualization":
        return "weak"
    if operation in {"association_test", "detect_anomalies", "summary_statistics"}:
        return "weak"
    return "weak"
