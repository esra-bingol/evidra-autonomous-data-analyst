"""V2.6 investigation report. Reads frozen run state; does not draft claims or run tools."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

SECTION_KEYS = (
    "executive_summary",
    "dataset_overview",
    "investigation_question",
    "investigation_plan",
    "research_trace",
    "key_findings",
    "evidence",
    "driver_decomposition",
    "visualizations",
    "statistical_results",
    "reviewer_decisions",
    "limitations",
    "recommended_next_investigations",
)

_SKIP_CHART_OPS = frozenset(
    {
        "inspect_dataset",
        "profile_dataset",
        "detect_capabilities",
        "quality_score",
        "current_coverage",
        "create_visualization",
        "generate_report",
    }
)


def build_investigation_report(run: dict[str, Any]) -> dict[str, Any]:
    evidence = list(run.get("evidence") or [])
    claims = list(run.get("claims") or [])
    reviews = list(run.get("reviews") or [])
    visualizations = _visualizations_from_evidence(evidence)
    findings = _findings(claims, reviews, visualizations)
    return {
        "schema_version": "v2.6",
        "source": "validated_investigation_state",
        "executive_summary": _executive_summary(run, claims),
        "dataset_overview": _dataset_overview(run, evidence),
        "investigation_question": run.get("question") or "",
        "investigation_plan": list(run.get("plan") or []),
        "research_trace": _research_trace(run),
        "key_findings": findings,
        "evidence": _evidence_index(evidence),
        "driver_decomposition": _driver_decomposition(run, evidence),
        "visualizations": visualizations,
        "statistical_results": _statistical_results(evidence),
        "reviewer_decisions": reviews,
        "limitations": _limitations(run, evidence, reviews),
        "recommended_next_investigations": _recommended_next(run),
    }


def _executive_summary(run: dict[str, Any], claims: list[dict[str, Any]]) -> str:
    decision = run.get("decision") or "abstain"
    stop = run.get("stop_reason") or ""
    lead = claims[0]["text"] if claims else "No published claim."
    driver = run.get("primary_driver")
    extra = f" Decision: {decision}."
    if driver:
        extra += f" Leading associated slice: {driver}."
    if stop:
        extra += f" Stop: {stop}."
    extra += " Chat is a short summary; this report is the full evidence-backed record."
    return lead + extra


def _dataset_overview(run: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    inspect = _first(evidence, "inspect_dataset")
    value = (inspect or {}).get("value") or {}
    caps = run.get("capabilities") or {}
    if not caps:
        cap_ev = _first(evidence, "detect_capabilities")
        caps = (cap_ev or {}).get("value") or {}
    present = [k for k, v in caps.items() if v]
    return {
        "path": run.get("path"),
        "n_rows": value.get("n_rows"),
        "n_cols": value.get("n_cols"),
        "n_tables": value.get("n_tables"),
        "columns": value.get("columns") or [],
        "roles": run.get("roles") or [],
        "capabilities_present": present,
        "evidence_id": (inspect or {}).get("evidence_id"),
    }


def _research_trace(run: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hyp in run.get("hypotheses") or []:
        rows.append(
            {
                "kind": "hypothesis",
                "template_id": hyp.get("template_id"),
                "status": hyp.get("status"),
                "hypothesis_id": hyp.get("hypothesis_id"),
            }
        )
    for step in run.get("research_steps") or []:
        rows.append(
            {
                "kind": "adaptive_step",
                "template_id": step.get("template_id"),
                "reason": step.get("reason"),
                "hypothesis_id": step.get("hypothesis_id"),
            }
        )
    for tr in run.get("traces") or []:
        rows.append(
            {
                "kind": "tool",
                "tool": tr.get("tool"),
                "ok": tr.get("ok"),
                "ms": tr.get("duration_ms"),
                "summary": tr.get("summary"),
            }
        )
    return rows


def _findings(
    claims: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    visualizations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_claim = {v.get("claim_id"): v for v in reviews}
    out = []
    for claim in claims:
        eids = list(claim.get("evidence_ids") or [])
        chart_ids = [
            viz["id"]
            for viz in visualizations
            if any(eid in (viz.get("evidence_ids") or []) for eid in eids)
        ]
        verdict = by_claim.get(claim.get("claim_id")) or {}
        out.append(
            {
                "claim_id": claim.get("claim_id"),
                "text": claim.get("text"),
                "kind": claim.get("kind"),
                "evidence_ids": eids,
                "chart_ids": chart_ids,
                "reviewer_decision": verdict.get("decision"),
                "reviewer_reason": verdict.get("reason"),
            }
        )
    return out


def _evidence_index(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for ev in evidence:
        rows.append(
            {
                "evidence_id": ev.get("evidence_id"),
                "operation": ev.get("operation"),
                "strength": ev.get("strength"),
                "source_columns": ev.get("source_columns") or [],
                "period": ev.get("period"),
            }
        )
    return rows


def _driver_decomposition(run: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    interaction = None
    for ev in evidence:
        if ev.get("operation") != "segment_by":
            continue
        dims = ((ev.get("filters") or {}).get("dimensions")) or []
        rows = ((ev.get("value") or {}).get("rows")) or []
        if len(dims) >= 2 and rows:
            interaction = ev
            break
    if not interaction:
        return {
            "primary_driver": run.get("primary_driver"),
            "rows": [],
            "evidence_id": None,
        }
    rows = ((interaction.get("value") or {}).get("rows")) or []
    ranked = sorted(rows, key=lambda r: abs(float(r.get("share_of_change") or 0)), reverse=True)
    return {
        "primary_driver": run.get("primary_driver"),
        "evidence_id": interaction.get("evidence_id"),
        "rows": ranked[:12],
    }


def _statistical_results(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for ev in evidence:
        if ev.get("operation") != "association_test":
            continue
        val = ev.get("value") or {}
        rows.append(
            {
                "evidence_id": ev.get("evidence_id"),
                "r": val.get("r"),
                "p_value": val.get("p_value"),
                "n": val.get("n"),
                "interpretation": val.get("interpretation") or "association_only",
            }
        )
    return rows


def _limitations(run: dict[str, Any], evidence: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> list[str]:
    notes = [
        "Published text is association language only; the report does not add causal claims.",
        "Figures bind to existing evidence values; they are not an independent source of numbers.",
        "The report generator does not create claims; only reviewer-published claims appear.",
    ]
    if (run.get("decision") or "") == "abstain" or (run.get("stop_reason") or "") == "abstain":
        notes.append("The investigation abstained; no unique driver is established.")
    if run.get("stop_reason") == "budget" or run.get("insufficient_kind") == "budget":
        notes.append("Research budget was exhausted before a stronger conclusion.")
    if run.get("insufficient_kind") == "multiple_plausible_drivers":
        notes.append("More than one segment meets the driver-share threshold.")
    cov = _first(evidence, "current_coverage")
    cov_val = (cov.get("value") or {}) if cov else {}
    if cov_val.get("truncated_current_period"):
        last = cov_val.get("current_last_observed")
        notes.append(f"Current window last observed {last}; coverage may be incomplete.")
    if any(v.get("decision") == "reject" for v in reviews):
        notes.append("At least one drafted claim was rejected by the reviewer and is not published.")
    return notes


def _recommended_next(run: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for step in run.get("research_steps") or []:
        reason = (step.get("reason") or "").strip()
        tmpl = step.get("template_id")
        if reason:
            items.append(f"Recorded follow-up ({tmpl}): {reason}")
    for hyp in run.get("hypotheses") or []:
        if hyp.get("status") == "skipped":
            items.append(f"Skipped closed template: {hyp.get('template_id')}")
    if (run.get("decision") or "") == "abstain" and not items:
        items.append("No further closed-template step is pending on this run.")
    if not items:
        items.append("Evidence was treated as sufficient; no extra template was queued.")
    return items[:8]


def _visualizations_from_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []
    for ev in evidence:
        op = ev.get("operation")
        if op in _SKIP_CHART_OPS or not ev.get("evidence_id"):
            continue
        built = _chart_for_evidence(ev)
        if built:
            built["id"] = f"viz-{len(charts) + 1}"
            charts.append(built)
    return charts


def _chart_for_evidence(ev: dict[str, Any]) -> dict[str, Any] | None:
    op = ev.get("operation")
    eid = ev["evidence_id"]
    val = ev.get("value") or {}
    if op == "compare_periods":
        prev, curr = val.get("previous"), val.get("current")
        if prev is None or curr is None:
            return None
        return _figure(
            kind="bar",
            purpose="category_comparison",
            title=f"Period totals ({val.get('metric') or 'metric'})",
            evidence_ids=[eid],
            fig=go.Figure(
                go.Bar(x=["previous", "current"], y=[float(prev), float(curr)])
            ),
        )
    if op == "segment_by":
        rows = val.get("rows") or []
        if len(rows) < 2:
            return None
        dims = ((ev.get("filters") or {}).get("dimensions")) or []
        if len(dims) >= 2:
            labeled = []
            for row in rows:
                label = " × ".join(str(row.get(d, "")) for d in dims)
                labeled.append((label, float(row.get("share_of_change") or 0)))
            labeled.sort(key=lambda p: abs(p[1]), reverse=True)
            labeled = labeled[:8]
            if not any(v != 0 for _, v in labeled):
                return None
            return _figure(
                kind="bar",
                purpose="driver_decomposition",
                title="Share of period change by slice",
                evidence_ids=[eid],
                fig=go.Figure(go.Bar(x=[a for a, _ in labeled], y=[b for _, b in labeled])),
            )
        dim = dims[0] if dims else next((k for k in rows[0] if k not in {"previous", "current", "change", "share_of_change"}), "segment")
        xs = [str(r.get(dim, "")) for r in rows[:12]]
        ys = [float(r.get("change") or 0) for r in rows[:12]]
        if not any(ys):
            return None
        return _figure(
            kind="bar",
            purpose="segment_comparison",
            title=f"Change by {dim}",
            evidence_ids=[eid],
            fig=go.Figure(go.Bar(x=xs, y=ys)),
        )
    if op == "decompose_volume_value":
        names, ys = [], []
        for key, label in (
            ("sales_change_pct", "sales %"),
            ("volume_change_pct", "volume %"),
            ("aov_change_pct", "AOV %"),
        ):
            if val.get(key) is None:
                continue
            names.append(label)
            ys.append(float(val[key]))
        if len(ys) < 2:
            return None
        return _figure(
            kind="bar",
            purpose="contribution",
            title="Volume vs value change",
            evidence_ids=[eid],
            fig=go.Figure(go.Bar(x=names, y=ys)),
        )
    if op == "detect_anomalies":
        monthly = val.get("monthly_z_outliers") or []
        if len(monthly) < 1:
            return None
        return _figure(
            kind="bar",
            purpose="distribution",
            title="Monthly z outliers (from evidence)",
            evidence_ids=[eid],
            fig=go.Figure(
                go.Bar(
                    x=[str(r.get("period")) for r in monthly],
                    y=[float(r.get("z")) for r in monthly],
                )
            ),
        )
    if op == "run_sql":
        rows = val.get("rows") or []
        if len(rows) < 2:
            return None
        keys = [k for k in rows[0].keys()]
        num_keys = [k for k in keys if all(_is_number(r.get(k)) for r in rows[:8])]
        cat_keys = [k for k in keys if k not in num_keys]
        if not num_keys or not cat_keys:
            return None
        xs = [str(r.get(cat_keys[0], "")) for r in rows[:12]]
        ys = [float(r.get(num_keys[0])) for r in rows[:12]]
        return _figure(
            kind="bar",
            purpose="category_comparison",
            title=f"{num_keys[0]} by {cat_keys[0]} (SQL evidence)",
            evidence_ids=[eid],
            fig=go.Figure(go.Bar(x=xs, y=ys)),
        )
    return None


def _figure(
    *,
    kind: str,
    purpose: str,
    title: str,
    evidence_ids: list[str],
    fig: go.Figure,
) -> dict[str, Any]:
    fig.update_layout(title=title, margin=dict(l=40, r=20, t=48, b=40), height=320)
    return {
        "kind": kind,
        "purpose": purpose,
        "title": title,
        "evidence_ids": evidence_ids,
        "plotly": fig.to_plotly_json(),
    }


def _first(evidence: list[dict[str, Any]], operation: str) -> dict[str, Any] | None:
    for ev in evidence:
        if ev.get("operation") == operation:
            return ev
    return None


def _is_number(val: Any) -> bool:
    if isinstance(val, bool) or val is None:
        return False
    try:
        float(val)
        return True
    except (TypeError, ValueError):
        return False
