from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis.eval.efficiency import overlay_row
from analysis.eval.runner import gate_evidence
from analysis.graph import run_investigation
from analysis.tools.schemas import Budget

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "evals" / "adaptive.json"


def load_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))["items"]


def _first_template(result: dict[str, Any]) -> str | None:
    hyps = result.get("hypotheses") or []
    if not hyps:
        return None
    return hyps[0].get("template_id") if isinstance(hyps[0], dict) else None


def _first_executed(result: dict[str, Any]) -> str | None:
    for hyp in result.get("hypotheses") or []:
        if isinstance(hyp, dict) and hyp.get("status") in {"tested", "dropped"}:
            return hyp.get("template_id")
    return None


def score_item(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    exp = item.get("expected") or {}
    plan = result.get("plan") or []
    steps = result.get("research_steps") or []
    reasons = " ".join(str(s.get("reason") or "") for s in steps if isinstance(s, dict))
    checks = {
        "decision": exp.get("decision") is None or result.get("decision") == exp["decision"],
        "primary_driver": (
            "primary_driver" not in exp or result.get("primary_driver") == exp["primary_driver"]
        ),
        "stop_reason": (
            "stop_reason" not in exp or result.get("stop_reason") == exp["stop_reason"]
        ),
        "next_research": (
            "next_research" not in exp or (("next_research" in plan) is bool(exp["next_research"]))
        ),
        "first_template": (
            "first_template" not in exp or _first_template(result) == exp["first_template"]
        ),
        "first_experiment": (
            "first_template" not in exp or _first_executed(result) == exp["first_template"]
        ),
        "insufficient_kind": (
            "insufficient_kind" not in exp
            or result.get("insufficient_kind") == exp["insufficient_kind"]
        ),
        "research_reason": (
            "research_reason_contains" not in exp
            or exp["research_reason_contains"].lower() in reasons.lower()
        ),
        "reviewer": bool(result.get("reviews")),
        "evidence_lock": gate_evidence(result),
    }
    actual = {
        "decision": result.get("decision"),
        "primary_driver": result.get("primary_driver"),
        "stop_reason": result.get("stop_reason"),
        "first_template": _first_template(result),
        "first_experiment": _first_executed(result),
        "next_research": "next_research" in plan,
        "research_steps": steps,
        "insufficient_kind": result.get("insufficient_kind"),
        "claim_texts": [c.get("text") for c in (result.get("claims") or []) if isinstance(c, dict)],
        "n_claims": len(result.get("claims") or []),
    }
    passed = all(checks.values())
    return {
        "id": item["id"],
        "pass": passed,
        "checks": checks,
        "actual": actual,
        "efficiency_row": overlay_row(
            case=item["id"],
            suite="adaptive",
            correct=passed,
            evidence_valid=gate_evidence(result),
            result=result,
        ),
    }


def run_adaptive() -> dict[str, Any]:
    rows = []
    for item in load_catalog():
        kwargs: dict[str, Any] = {}
        if item.get("budget"):
            kwargs["budget"] = Budget(**item["budget"])
        result = run_investigation(ROOT / item["dataset"], item["question"], **kwargs)
        rows.append(score_item(item, result))
    return {
        "n_items": len(rows),
        "n_pass": sum(1 for r in rows if r["pass"]),
        "pass": all(r["pass"] for r in rows),
        "items": rows,
    }


def main(argv: list[str] | None = None) -> None:
    del argv
    report = run_adaptive()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
