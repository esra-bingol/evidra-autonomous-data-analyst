from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from analysis.capabilities import detect_capabilities
from analysis.load import load_tabular
from analysis.periods import compare_periods, current_coverage, infer_period_windows
from analysis.profiler import profile_dataset
from analysis.quality import quality_score
from analysis.roles import column_with_semantic, columns_with_role, infer_roles
from analysis.segments import segment_by
from analysis.visualization import create_visualization
from analysis.volume_value import decompose_volume_value

NOISE_PCT = 5.0
DRIVER_SHARE_MIN = 0.5


def investigate(path: str | Path) -> dict[str, Any]:
    df = load_tabular(path)
    profile = profile_dataset(df)
    roles = profile.value["roles"]
    caps = detect_capabilities(roles)
    quality = quality_score(df)
    time_col = columns_with_role(roles, "time")[0]
    metric = column_with_semantic(roles, "sales") or columns_with_role(roles, "metric")[0]
    windows = infer_period_windows(df[time_col])
    comparison = compare_periods(df, metric=metric, time_col=time_col, windows=windows)
    coverage = current_coverage(df, time_col=time_col)
    volume = decompose_volume_value(df, metric=metric, time_col=time_col, windows=windows)

    dims = columns_with_role(roles, "dimension")
    region = next((c for c in dims if "region" in c.lower()), dims[0] if dims else None)
    category = next((c for c in dims if "categor" in c.lower()), dims[1] if len(dims) > 1 else None)

    interaction = None
    if region and category:
        interaction = segment_by(df, [region, category], metric=metric, time_col=time_col, windows=windows)

    change_pct = comparison.value["change_pct"]
    decision = "primary_driver"
    primary_driver = None
    stop = "strong_evidence"
    vol = volume.value
    aov_pct = abs(vol["aov_change_pct"] or 0)
    vol_pct = abs(vol["volume_change_pct"] or 0)

    if coverage.value["truncated_current_period"]:
        decision = "data_artefact"
        stop = "abstain"
    elif change_pct is not None and abs(change_pct) <= NOISE_PCT:
        decision = "abstain"
        stop = "abstain"
    elif aov_pct >= 20 and vol_pct <= 10 and aov_pct > vol_pct:
        decision = "value_not_volume"
        primary_driver = "AOV"
    elif interaction and interaction.value["rows"]:
        top = interaction.value["rows"][0]
        share = abs(top["share_of_change"]) if comparison.value["change"] else 0.0
        if share >= DRIVER_SHARE_MIN and region and category:
            primary_driver = f"{top[region]} × {top[category]}"
        else:
            decision = "abstain"
            stop = "abstain"
            primary_driver = None
    else:
        decision = "abstain"
        stop = "abstain"

    charts = [
        create_visualization(df, kind="trend").to_dict(),
        create_visualization(df, kind="segment").to_dict(),
    ]

    return {
        "path": str(path),
        "decision": decision,
        "primary_driver": primary_driver,
        "stop": stop,
        "compare_periods": comparison.to_dict(),
        "coverage": coverage.to_dict(),
        "volume_value": volume.to_dict(),
        "interaction": None if interaction is None else interaction.to_dict(),
        "capabilities": caps.to_dict(),
        "quality": quality.to_dict(),
        "charts": charts,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evidra analysis engine (no LLM)")
    parser.add_argument("--data", required=True, help="CSV or Excel path")
    args = parser.parse_args(argv)
    result = investigate(args.data)
    slim = {
        "decision": result["decision"],
        "primary_driver": result["primary_driver"],
        "stop": result["stop"],
        "change_pct": result["compare_periods"]["value"]["change_pct"],
        "capabilities": result["capabilities"]["value"],
    }
    print(json.dumps(slim, indent=2, ensure_ascii=False))
    if result["primary_driver"]:
        print(f"primary_driver: {result['primary_driver']}")


if __name__ == "__main__":
    main()
