from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from analysis.eval.runner import _CAUSAL
from analysis.graph import run_investigation

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "evals" / "adversarial.json"

FAILURE_CLASSES = {
    "A": "real_bug",
    "B": "current_capability_limit",
    "C": "needs_v2_4_adaptive_research",
    "D": "needs_new_tool_or_capability",
}


def load_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))["items"]


def _blob(result: dict[str, Any]) -> str:
    return json.dumps(
        {"claims": result.get("claims") or [], "reviews": result.get("reviews") or []},
        ensure_ascii=False,
    )


def actual_behavior(result: dict[str, Any]) -> dict[str, Any]:
    reviews = result.get("reviews") or []
    claims = result.get("claims") or []
    hyps = result.get("hypotheses") or []
    return {
        "decision": result.get("decision"),
        "primary_driver": result.get("primary_driver"),
        "stop_reason": result.get("stop_reason"),
        "n_hypotheses": len(hyps),
        "n_claims": len(claims),
        "claim_texts": [c.get("text") for c in claims if isinstance(c, dict)],
        "review_decisions": [r.get("decision") for r in reviews if isinstance(r, dict)],
        "causal_language_in_output": bool(_CAUSAL.search(_blob(result))),
    }


def _eval_checks(checks: dict[str, Any], result: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if checks.get("no_causal_language") and actual["causal_language_in_output"]:
        failed.append("no_causal_language")
    if checks.get("hypotheses_empty") and result.get("hypotheses"):
        failed.append("hypotheses_empty")
    allowed = checks.get("decision_in")
    if allowed is not None and actual["decision"] not in allowed:
        failed.append(f"decision_in:{allowed} actual={actual['decision']}")
    forbidden = checks.get("decision_not_in")
    if forbidden is not None and actual["decision"] in forbidden:
        failed.append(f"decision_not_in:{forbidden} actual={actual['decision']}")
    if checks.get("no_unique_primary_driver") and actual.get("primary_driver"):
        failed.append(f"no_unique_primary_driver actual={actual['primary_driver']}")
    return failed


def score_item(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    actual = actual_behavior(result)
    failed = _eval_checks(item.get("checks") or {}, result, actual)
    passed = not failed
    klass = item.get("if_fail_class")
    row = {
        "id": item["id"],
        "category": item["category"],
        "must_pass": bool(item.get("must_pass")),
        "expected_behavior": item["expected_behavior"],
        "actual_behavior": actual,
        "pass": passed,
        "failure_reason": None if passed else "; ".join(failed),
        "failure_class": None if passed else klass,
        "failure_class_label": None if passed else FAILURE_CLASSES.get(klass, klass),
    }
    return row


def run_adversarial() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in load_catalog():
        path = ROOT / item["dataset"]
        result = run_investigation(path, item["question"])
        rows.append(score_item(item, result))
    must = [r for r in rows if r["must_pass"]]
    reported = [r for r in rows if not r["must_pass"]]
    return {
        "n_items": len(rows),
        "must_pass_ok": all(r["pass"] for r in must),
        "n_must_pass": len(must),
        "n_must_pass_ok": sum(1 for r in must if r["pass"]),
        "n_reported": len(reported),
        "n_reported_pass": sum(1 for r in reported if r["pass"]),
        "n_reported_fail": sum(1 for r in reported if not r["pass"]),
        "items": rows,
    }


def main(argv: list[str] | None = None) -> None:
    del argv
    report = run_adversarial()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["must_pass_ok"] else 1)


if __name__ == "__main__":
    main()
