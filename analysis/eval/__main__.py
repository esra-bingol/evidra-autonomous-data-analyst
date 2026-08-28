from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis.eval.adaptive import run_adaptive
from analysis.eval.adversarial import run_adversarial
from analysis.eval.efficiency import build_report, collect_rows
from analysis.eval.olist_rubric import run_olist_rubric
from analysis.eval.runner import run_suite

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evidra V1 eval suite (no UI)")
    parser.add_argument(
        "--out",
        default=str(ROOT / "evals" / "out" / "last_report.json"),
        help="JSON report path",
    )
    args = parser.parse_args(argv)
    report = run_suite()
    olist = run_olist_rubric()
    adversarial = run_adversarial()
    adaptive = run_adaptive()
    report["olist_rubric"] = olist
    report["adversarial"] = adversarial
    report["adaptive"] = adaptive
    efficiency = build_report(collect_rows(report, olist, adversarial, adaptive))
    report["efficiency"] = {
        "efficiency_enforced": efficiency["efficiency_enforced"],
        "gate_order": efficiency["gate_order"],
        "proposed_thresholds": efficiency["proposed_thresholds"],
        "n_eligible": efficiency["n_eligible"],
        "n_blocked": efficiency["n_blocked"],
        "table": efficiency["table"],
    }
    report["pass"] = bool(
        report["pass"]
        and olist.get("pass", True)
        and adversarial.get("must_pass_ok", True)
        and adaptive.get("pass", True)
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log_path = out.parent / "efficiency_log.jsonl"
    with log_path.open("w", encoding="utf-8") as fh:
        for row in report.get("efficiency_log") or []:
            fh.write(json.dumps(row) + "\n")
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "n_pass": report["n_pass"],
                "n_scored": report["n_scored"],
                "olist_rubric": {
                    "skipped": (report.get("olist_rubric") or {}).get("skipped"),
                    "pass": (report.get("olist_rubric") or {}).get("pass"),
                },
                "adversarial": {
                    "must_pass_ok": (report.get("adversarial") or {}).get("must_pass_ok"),
                    "n_reported_fail": (report.get("adversarial") or {}).get("n_reported_fail"),
                },
                "adaptive": {
                    "pass": (report.get("adaptive") or {}).get("pass"),
                    "n_pass": (report.get("adaptive") or {}).get("n_pass"),
                },
                "efficiency": {
                    "enforced": (report.get("efficiency") or {}).get("efficiency_enforced"),
                    "n_eligible": (report.get("efficiency") or {}).get("n_eligible"),
                    "n_blocked": (report.get("efficiency") or {}).get("n_blocked"),
                    "proposed_max_experiments": (
                        ((report.get("efficiency") or {}).get("proposed_thresholds") or {})
                        .get("experiments")
                        or {}
                    ).get("proposed_max"),
                },
                "out": str(out),
            },
            indent=2,
        )
    )
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
