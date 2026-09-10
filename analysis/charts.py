"""Evidence-bound chart selection. Does not analyze data or invent numbers."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from analysis.policy import detect_intent

MAX_CHARTS = 4
_SKIP_DIM = {"previous", "current", "change", "share_of_change"}


def build_charts(run: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = list(run.get("evidence") or [])
    decision = run.get("decision") or "abstain"
    intent = detect_intent(str(run.get("question") or ""))
    picks: list[dict[str, Any]] = []

    cmp = _first(evidence, "compare_periods")
    vol = _first(evidence, "decompose_volume_value")
    seg1 = _last_segment(evidence, two_dim=False)
    seg2 = _last_segment(evidence, two_dim=True)
    anom = _first(evidence, "detect_anomalies")

    if intent == "ranking" and seg1:
        picks.append(_segment_bar(run, seg1))
    else:
        if cmp and decision != "association":
            picks.append(_trend_line(run, cmp))
        if decision == "primary_driver" and seg2:
            picks.append(_contribution(run, seg2))
        elif intent != "ranking" and seg1 and decision not in {"abstain", "association"}:
            picks.append(_segment_bar(run, seg1))
        if vol and decision in {"primary_driver", "value_not_volume"}:
            picks.append(_volume_aov(run, vol))
        if decision == "data_artefact" and anom:
            picks.append(_anomaly_bar(run, anom))

    out: list[dict[str, Any]] = []
    for chart in picks:
        if not chart:
            continue
        chart["id"] = f"viz-{len(out) + 1}"
        out.append(chart)
        if len(out) >= MAX_CHARTS:
            break
    return out


def _trend_line(run: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any] | None:
    val = ev.get("value") or {}
    prev, curr = val.get("previous"), val.get("current")
    if prev is None or curr is None:
        return None
    period = ev.get("period") or {}
    x0 = (period.get("previous") or {}).get("end") or "önceki dönem"
    x1 = (period.get("current") or {}).get("end") or "güncel dönem"
    metric = val.get("metric") or "metrik"
    fig = go.Figure(
        go.Scatter(
            x=[str(x0), str(x1)],
            y=[float(prev), float(curr)],
            mode="lines+markers",
        )
    )
    return _pack(
        run,
        kind="line",
        purpose="trend",
        title=f"{metric} eğilimi",
        evidence_ids=[ev["evidence_id"]],
        fig=fig,
    )


def _segment_bar(run: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any] | None:
    rows = (ev.get("value") or {}).get("rows") or []
    dims = list((ev.get("filters") or {}).get("dimensions") or [])
    if len(rows) < 2:
        return None
    dim = dims[0] if dims else next((k for k in rows[0] if k not in _SKIP_DIM), "segment")
    xs = [str(r.get(dim, "")) for r in rows[:12]]
    ys = [float(r.get("change") or 0) for r in rows[:12]]
    if not any(ys):
        return None
    fig = go.Figure(go.Bar(x=xs, y=ys))
    return _pack(
        run,
        kind="bar",
        purpose="segment_comparison",
        title=f"{dim} karşılaştırması",
        evidence_ids=[ev["evidence_id"]],
        fig=fig,
    )


def _contribution(run: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any] | None:
    rows = (ev.get("value") or {}).get("rows") or []
    dims = list((ev.get("filters") or {}).get("dimensions") or [])
    if len(rows) < 2 or len(dims) < 2:
        return None
    labeled = []
    for row in rows:
        label = " × ".join(str(row.get(d, "")) for d in dims)
        labeled.append((label, float(row.get("change") or 0)))
    labeled.sort(key=lambda p: abs(p[1]), reverse=True)
    labeled = labeled[:6]
    if not any(v != 0 for _, v in labeled):
        return None
    fig = go.Figure(
        go.Waterfall(
            x=[a for a, _ in labeled],
            y=[b for _, b in labeled],
            measure=["relative"] * len(labeled),
        )
    )
    return _pack(
        run,
        kind="waterfall",
        purpose="contribution",
        title="Değişime katkı",
        evidence_ids=[ev["evidence_id"]],
        fig=fig,
    )


def _volume_aov(run: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any] | None:
    val = ev.get("value") or {}
    names, ys = [], []
    for key, label in (
        ("volume_change_pct", "hacim %"),
        ("aov_change_pct", "sepet (AOV) %"),
    ):
        if val.get(key) is None:
            continue
        names.append(label)
        ys.append(float(val[key]))
    if len(ys) < 2:
        return None
    fig = go.Figure(go.Bar(x=names, y=ys))
    return _pack(
        run,
        kind="bar",
        purpose="metric_comparison",
        title="Hacim ve sepet tutarı",
        evidence_ids=[ev["evidence_id"]],
        fig=fig,
    )


def _anomaly_bar(run: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any] | None:
    monthly = (ev.get("value") or {}).get("monthly_z_outliers") or []
    if len(monthly) < 1:
        return None
    fig = go.Figure(
        go.Bar(
            x=[str(r.get("period")) for r in monthly],
            y=[float(r.get("z")) for r in monthly],
        )
    )
    return _pack(
        run,
        kind="bar",
        purpose="distribution",
        title="Aykırı dönemler",
        evidence_ids=[ev["evidence_id"]],
        fig=fig,
    )


def _pack(
    run: dict[str, Any],
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
        "claim_ids": _claim_ids_for(run, evidence_ids),
        "plotly": fig.to_plotly_json(),
    }


def _claim_ids_for(run: dict[str, Any], evidence_ids: list[str]) -> list[str]:
    wanted = set(evidence_ids)
    rejected = {
        v.get("claim_id")
        for v in (run.get("reviews") or [])
        if v.get("decision") == "reject"
    }
    ids: list[str] = []
    for claim in run.get("claims") or []:
        cid = claim.get("claim_id")
        if not cid or cid in rejected:
            continue
        if wanted & set(claim.get("evidence_ids") or []):
            ids.append(cid)
    return ids


def _first(evidence: list[dict[str, Any]], operation: str) -> dict[str, Any] | None:
    for ev in evidence:
        if ev.get("operation") == operation and ev.get("evidence_id"):
            return ev
    return None


def _last_segment(evidence: list[dict[str, Any]], two_dim: bool) -> dict[str, Any] | None:
    items = []
    for ev in evidence:
        if ev.get("operation") != "segment_by" or not ev.get("evidence_id"):
            continue
        dims = (ev.get("filters") or {}).get("dimensions") or []
        if two_dim and len(dims) >= 2:
            items.append(ev)
        if not two_dim and len(dims) == 1:
            items.append(ev)
    return items[-1] if items else None
