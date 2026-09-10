"""V2.11 investigation report. Reads frozen run state; does not draft claims or run tools."""

from __future__ import annotations

import re
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

PLAN_LABELS = {
    "inspect_dataset": "Veri seti incelendi",
    "profile_dataset": "Kolonlar ve roller profillendi",
    "detect_capabilities": "Yetenekler belirlendi",
    "intersect": "Soru ile yetenekler kesiştirildi",
    "rank_hypotheses": "Hipotezler sıralandı",
    "experiment_loop": "Deneyler çalıştırıldı",
    "score": "Kanıtlar puanlandı",
    "assess_evidence": "Kanıt yeterliliği değerlendirildi",
    "next_research": "Kapalı şablonla ek adım atıldı",
    "stop": "Araştırma durdu",
    "validate_claims": "İddialar doğrulandı",
    "review_claims": "Reviewer denetimi uygulandı",
    "report": "Rapor üretildi",
}

DECISION_LABELS = {
    "primary_driver": "Öne çıkan dilim destekleniyor",
    "value_not_volume": "Sepet tutarı, hacim değil",
    "data_artefact": "Veri kalitesi işareti",
    "ranking": "Sıralama",
    "association": "İlişki",
    "abstain": "Yoğunlaşmış sürücü yok",
}

OPERATION_LABELS = {
    "compare_periods": "Dönem karşılaştırması",
    "segment_by": "Dilim karşılaştırması",
    "decompose_volume_value": "Hacim ve sepet ayrıştırması",
    "association_test": "İlişki testi",
    "detect_anomalies": "Anomali taraması",
    "current_coverage": "Dönem kapsamı",
    "inspect_dataset": "Veri seti özeti",
    "profile_dataset": "Profil",
    "detect_capabilities": "Yetenekler",
}

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
_ENGINE_LEAK = re.compile(
    r"\b(associated|primary_driver|share_of_change|compare_periods|segment_by|"
    r"decompose_volume_value|value_not_volume)\b",
    re.I,
)


def build_investigation_report(run: dict[str, Any]) -> dict[str, Any]:
    evidence = list(run.get("evidence") or [])
    claims = list(run.get("claims") or [])
    reviews = list(run.get("reviews") or [])
    visualizations = _visualizations_from_evidence(evidence)
    findings = _findings(run, claims, reviews, visualizations)
    headlines = _headline_findings(run, evidence)
    return {
        "schema_version": "v2.11",
        "source": "validated_investigation_state",
        "title": _title(run),
        "decision_label": DECISION_LABELS.get(run.get("decision") or "abstain", run.get("decision") or "abstain"),
        "executive_summary": _executive_summary(run),
        "headline_findings": headlines,
        "dataset_overview": _dataset_overview(run, evidence),
        "investigation_question": run.get("question") or "",
        "investigation_plan": list(run.get("plan") or []),
        "plan_readable": _plan_readable(run.get("plan") or []),
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


def _title(run: dict[str, Any]) -> str:
    scope = run.get("scope") or {}
    if isinstance(scope, dict) and scope:
        values = [str(v) for v in scope.values() if v]
        if len(values) == 1:
            return f"{values[0]} dilimi incelemesi"
        if len(values) >= 2:
            return f"{values[0]} × {values[1]} dilimi incelemesi"
    q = str(run.get("question") or "").lower()
    if "satış" in q or "sales" in q:
        return "Satış değişimi incelemesi"
    if "teslimat" in q or "delivery" in q:
        return "Teslimat incelemesi"
    return "Evidra incelemesi"


def _executive_summary(run: dict[str, Any]) -> str:
    decision = run.get("decision") or "abstain"
    change = _change_pct(run)
    driver = run.get("primary_driver")
    parts: list[str] = []
    if change is not None:
        parts.append(_change_sentence(change))
    if decision == "primary_driver" and driver:
        parts.append(f"En güçlü desteklenen sinyal {_driver_phrase(str(driver))}.")
    elif decision == "value_not_volume":
        parts.append("Bulgu sipariş hacminden çok ortalama sepet tutarı ile ilişkili görünüyor.")
    elif decision == "data_artefact":
        parts.append("Görünen değişim eksik bir güncel pencereyle birlikte görülüyor.")
    elif decision == "ranking" and driver:
        parts.append(f"Karşılaştırmada öne çıkan dilim {_driver_phrase(str(driver))}.")
    elif decision == "association":
        parts.append("Bulgu bir ilişki ifadesidir, nedensellik değil.")
    elif decision == "abstain":
        if not parts:
            parts.append("Bu incelemeden yoğunlaşmış bir sürücü desteklenmiyor.")
        else:
            parts.append("Yoğunlaşmış bir sürücü desteklenmiyor.")
    text = " ".join(parts)
    if _ENGINE_LEAK.search(text):
        return "Bu incelemenin yayımlanan sonucu mevcut kanıtlara bağlıdır; motor jargonu rapora yazılmaz."
    return text


def _headline_findings(run: dict[str, Any], _evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decision = run.get("decision") or "abstain"
    driver = run.get("primary_driver")
    vol = _volume_value(run)
    items: list[dict[str, Any]] = []

    def add(text: str, ops: set[str]) -> None:
        items.append(
            {
                "n": len(items) + 1,
                "text": text,
                "evidence_ids": _evidence_ids(run, ops),
            }
        )

    if decision == "primary_driver" and driver:
        add(f"{driver} — en güçlü desteklenen sinyal", {"segment_by"})
        volume = vol.get("volume_change_pct")
        aov = vol.get("aov_change_pct")
        if volume is not None and float(volume) < 0:
            add("Satış hacmi daraldı", {"decompose_volume_value"})
        if aov is not None and float(aov) > 0:
            add("Ortalama sepet tutarı hafif arttı", {"decompose_volume_value"})
        elif aov is not None and float(aov) < 0:
            add("Ortalama sepet tutarı azaldı", {"decompose_volume_value"})
    elif decision == "value_not_volume":
        add("Değişim sipariş hacminden çok sepet tutarı ile ilişkili", {"decompose_volume_value"})
    elif decision == "ranking" and driver:
        add(f"Öne çıkan dilim: {_driver_phrase(str(driver))}", {"segment_by"})
    elif decision == "association":
        add("Ölçülen ilişki nedensellik iddiası taşımaz", {"association_test"})
    elif decision == "data_artefact":
        add("Güncel dönem penceresi eksik olabilir", {"current_coverage"})
    else:
        add("Yoğunlaşmış bir sürücü desteklenmiyor", {"compare_periods"})
    return items[:6]


def _plan_readable(plan: list[str]) -> list[str]:
    return [PLAN_LABELS.get(step, step) for step in plan]


def _change_pct(run: dict[str, Any]) -> float | None:
    for ev in run.get("evidence") or []:
        if ev.get("operation") == "compare_periods":
            val = ev.get("value") or {}
            if val.get("change_pct") is not None:
                return float(val["change_pct"])
    return None


def _volume_value(run: dict[str, Any]) -> dict[str, Any]:
    for ev in run.get("evidence") or []:
        if ev.get("operation") == "decompose_volume_value":
            return ev.get("value") or {}
    return {}


def _evidence_ids(run: dict[str, Any], operations: set[str]) -> list[str]:
    return [
        ev["evidence_id"]
        for ev in (run.get("evidence") or [])
        if ev.get("operation") in operations and ev.get("evidence_id")
    ]


def _change_sentence(change: float) -> str:
    if change < 0:
        return f"Satışlar bu dönemde %{_fmt(abs(change))} azaldı."
    if change > 0:
        return f"Satışlar bu dönemde %{_fmt(change)} arttı."
    return "Satışlar bu dönemde belirgin değişmedi."


def _driver_phrase(label: str) -> str:
    parts = [p.strip() for p in re.split(r"\s*[×x]\s*", label) if p.strip()]
    if len(parts) == 2:
        return f"{parts[0]} bölgesindeki {parts[1]}"
    return label


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    n = float(value)
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    text = f"{n:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


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
    run: dict[str, Any],
    claims: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    visualizations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_claim = {v.get("claim_id"): v for v in reviews}
    out = []
    for claim in claims:
        verdict = by_claim.get(claim.get("claim_id")) or {}
        if verdict.get("decision") == "reject":
            continue
        eids = list(claim.get("evidence_ids") or [])
        chart_ids = [
            viz["id"]
            for viz in visualizations
            if any(eid in (viz.get("evidence_ids") or []) for eid in eids)
        ]
        text = str(claim.get("text") or "")
        headline = re.sub(r"\bis associated with\b", "ile ilişkili görünüyor", text, flags=re.I)
        headline = re.sub(r"\bassociated\b", "ilişkili", headline, flags=re.I)
        out.append(
            {
                "claim_id": claim.get("claim_id"),
                "text": text,
                "headline": headline,
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
        op = ev.get("operation")
        rows.append(
            {
                "evidence_id": ev.get("evidence_id"),
                "operation": op,
                "operation_label": OPERATION_LABELS.get(op or "", op),
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
        driver = run.get("primary_driver")
        return {
            "primary_driver": driver,
            "primary_driver_label": _driver_phrase(str(driver)) if driver else None,
            "rows": [],
            "evidence_id": None,
        }
    rows = ((interaction.get("value") or {}).get("rows")) or []
    ranked = sorted(rows, key=lambda r: abs(float(r.get("share_of_change") or 0)), reverse=True)
    driver = run.get("primary_driver")
    return {
        "primary_driver": driver,
        "primary_driver_label": _driver_phrase(str(driver)) if driver else None,
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
        "Yayımlanan metin ilişki dilindedir; rapor nedensel iddia eklemez.",
        "Grafikler mevcut kanıt değerlerine bağlıdır; bağımsız sayı kaynağı değillerdir.",
        "Rapor üreticisi yeni iddia oluşturmaz; yalnızca reviewer’dan geçen iddialar görünür.",
    ]
    if (run.get("decision") or "") == "abstain" or (run.get("stop_reason") or "") == "abstain":
        notes.append("Yoğunlaşmış bir sürücü bu incelemede desteklenmiyor.")
    if run.get("stop_reason") == "budget" or run.get("insufficient_kind") == "budget":
        notes.append("Araştırma bütçesi daha güçlü bir sonuca ulaşmadan doldu.")
    if run.get("insufficient_kind") == "multiple_plausible_drivers":
        notes.append("Birden fazla dilim sürücü eşiğini geçiyor.")
    cov = _first(evidence, "current_coverage")
    cov_val = (cov.get("value") or {}) if cov else {}
    if cov_val.get("truncated_current_period"):
        last = cov_val.get("current_last_observed")
        notes.append(f"Güncel dönem penceresi eksik olabilir (son gözlem: {last}).")
    if any(v.get("decision") == "reject" for v in reviews):
        notes.append("En az bir taslak iddia reviewer tarafından reddedildi ve yayımlanmadı.")
    return notes


def _recommended_next(run: dict[str, Any]) -> list[str]:
    items: list[str] = []
    driver = run.get("primary_driver")
    if driver:
        items.append(f"{_driver_phrase(str(driver))} dilimini ayrı bir hipotez olarak incele.")
    vol = _volume_value(run)
    volume = vol.get("volume_change_pct")
    if volume is not None and float(volume) < 0:
        items.append("Hacim daralmasının hangi alt dilimde yoğunlaştığını incele.")
    if run.get("scope"):
        items.append("Kapsamı genişletip tüm tabloya dön.")
    if (run.get("decision") or "") == "abstain":
        items.append("Mevcut yeteneklerle yanıtlanabilecek başka bir iş sorusu sor.")
    if not items:
        items.append("Detaylı raporu ve kanıt listesini gözden geçir.")
    return items[:6]


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
            title=f"Dönem toplamları ({val.get('metric') or 'metrik'})",
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
                title="Dilimlerin değişim payı",
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
            title=f"{dim} bazında değişim",
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
            title="Hacim ve sepet tutarı değişimi",
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
            title="Aylık z sapmaları (kanıttan)",
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
