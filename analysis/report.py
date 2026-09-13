"""Investigation report. Reads frozen run state; does not draft claims or run tools."""

from __future__ import annotations

import re
from typing import Any

from analysis.charts import build_charts
from analysis.response import abstain_explanation, compose_response

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

STEP_LABELS = {
    "inspect_dataset": "Tabloyu okudum: kaç satır var, hangi kolonlar hangi rolü taşıyor.",
    "profile_dataset": "Tarih, tutar ve kırılım kolonlarını işaretledim.",
    "current_coverage": "Güncel dönemin tam mı yoksa yarım mı olduğunu kontrol ettim.",
    "compare_periods": "Önceki dönem ile güncel dönemi aynı ölçüyle karşılaştırdım.",
    "decompose_volume_value": (
        "Değişimi ikiye ayırdım: sipariş sayısı mı değişti, sipariş başına tutar mı?"
    ),
    "detect_anomalies": "Sıra dışı görünen dönemleri işaretledim.",
    "association_test": "İki ölçünün birlikte hareket edip etmediğini test ettim.",
    "join_assemble": "İlgili tabloları ortak anahtar üzerinden birleştirdim.",
    "run_sql": "Soruya karşılık gelen sorguyu tablo üzerinde çalıştırdım.",
}

DECISION_LABELS = {
    "primary_driver": "Öne çıkan dilim destekleniyor",
    "value_not_volume": "Sepet tutarı, hacim değil",
    "data_artefact": "Veri kalitesi işareti",
    "ranking": "Sıralama",
    "association": "İlişki",
    "abstain": "Belirgin yoğunlaşma yok",
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

_ENGINE_LEAK = re.compile(
    r"\b(associated|primary_driver|share_of_change|compare_periods|segment_by|"
    r"decompose_volume_value|value_not_volume)\b",
    re.I,
)


def build_investigation_report(run: dict[str, Any]) -> dict[str, Any]:
    evidence = list(run.get("evidence") or [])
    claims = list(run.get("claims") or [])
    reviews = list(run.get("reviews") or [])
    visualizations = build_charts(run)
    findings = _findings(run, claims, reviews, visualizations)
    headlines = _headline_findings(run, evidence)
    return {
        "schema_version": "v2.12",
        "source": "validated_investigation_state",
        "title": _title(run),
        "decision_label": DECISION_LABELS.get(run.get("decision") or "abstain", run.get("decision") or "abstain"),
        "executive_summary": _executive_summary(run),
        "headline_findings": headlines,
        "dataset_overview": _dataset_overview(run, evidence),
        "investigation_question": run.get("question") or "",
        "investigation_plan": list(run.get("plan") or []),
        "plan_readable": _plan_readable(run),
        "research_trace": _research_trace(run),
        "key_findings": findings,
        "evidence": _evidence_index(evidence),
        "driver_decomposition": _driver_decomposition(run, evidence),
        "visualizations": visualizations,
        "statistical_results": _statistical_results(evidence),
        "reviewer_decisions": reviews,
        "limitations": _limitations(run, evidence, reviews),
        "recommended_next_investigations": _recommended_next(run),
        "kpis": _kpis(run, evidence),
        "slice_table": _slice_table(evidence),
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
    if "ücret" in q or "fare" in q:
        return "Ücret değişimi incelemesi"
    if "satış" in q or "sales" in q:
        return "Satış değişimi incelemesi"
    if "teslimat" in q or "delivery" in q:
        return "Teslimat incelemesi"
    return "Evidra incelemesi"


def _executive_summary(run: dict[str, Any]) -> str:
    """Same prose the analyst reads in chat, so the two never disagree."""
    if (run.get("decision") or "abstain") == "abstain":
        text = abstain_explanation(run)
    else:
        text = compose_response(run).answer
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
        top = next((r for r in _slice_table(_evidence) if r.get("label") == driver), None)
        if top and top.get("share_pct") is not None:
            add(
                f"Değişim en çok {driver} diliminde: "
                f"{_fmt(top.get('previous'))} → {_fmt(top.get('current'))}, "
                f"toplam değişimin %{_fmt(top.get('share_pct'))} kadarı burada",
                {"segment_by"},
            )
        else:
            add(f"Değişim en çok {driver} diliminde toplanıyor", {"segment_by"})
        volume = vol.get("volume_change_pct")
        aov = vol.get("aov_change_pct")
        if volume is not None and aov is not None:
            add(
                f"Sipariş sayısı %{_fmt(abs(float(volume)))} "
                f"{'azaldı' if float(volume) < 0 else 'arttı' if float(volume) > 0 else 'değişmedi'}, "
                f"ortalama sepet tutarı %{_fmt(abs(float(aov)))} "
                f"{'azaldı' if float(aov) < 0 else 'arttı' if float(aov) > 0 else 'değişmedi'}",
                {"decompose_volume_value"},
            )
    elif decision == "value_not_volume":
        aov = vol.get("aov_change_pct")
        volume = vol.get("volume_change_pct")
        if aov is not None and volume is not None:
            add(
                f"Sipariş sayısı neredeyse sabit (%{_fmt(abs(float(volume)))}), "
                f"düşüş sepet tutarında (%{_fmt(abs(float(aov)))})",
                {"decompose_volume_value"},
            )
        else:
            add("Değişim sipariş hacminden çok sepet tutarı ile ilişkili", {"decompose_volume_value"})
    elif decision == "ranking" and driver:
        add(f"Öne çıkan dilim: {_driver_phrase(str(driver))}", {"segment_by"})
    elif decision == "association":
        add("Ölçülen ilişki nedensellik iddiası taşımaz", {"association_test"})
    elif decision == "data_artefact":
        add("Güncel dönem penceresi eksik olabilir", {"current_coverage"})
    else:
        add("Değişim yayılmış; tek bir kaynak işaretlenmedi", {"compare_periods", "segment_by"})
    return items[:6]


def _plan_readable(run: dict[str, Any]) -> list[str]:
    """What was done to the data, in order, not which graph nodes ran."""
    steps: list[str] = []

    def add(text: str) -> None:
        if text not in steps:
            steps.append(text)

    for ev in run.get("evidence") or []:
        op = ev.get("operation")
        if op == "segment_by":
            dims = [str(d) for d in ((ev.get("filters") or {}).get("dimensions") or [])]
            label = " ve ".join(dims) if dims else "mevcut"
            add(f"{label} kırılımlarını tek tek tarayıp hangi dilimin ne kadar değiştiğine baktım.")
        elif op in STEP_LABELS:
            add(STEP_LABELS[op])
    if not steps:
        return [PLAN_LABELS.get(step, step) for step in run.get("plan") or []]
    if run.get("reviews"):
        add("Her cümleyi hesaplanan kanıta bağladım; bağlanamayan cümleyi yayımlamadım.")
    return steps


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


def _change_sentence(change: float, run: dict[str, Any] | None = None) -> str:
    metric = ""
    for ev in (run or {}).get("evidence") or []:
        if ev.get("operation") == "compare_periods":
            metric = str((ev.get("value") or {}).get("metric") or "").lower()
            break
    noun = "Ücretler" if "fare" in metric else "Satışlar"
    if change < 0:
        return f"{noun} bu dönemde %{_fmt(abs(change))} azaldı."
    if change > 0:
        return f"{noun} bu dönemde %{_fmt(change)} arttı."
    return f"{noun} bu dönemde belirgin değişmedi."


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
    source = _best_segment(evidence)
    driver = run.get("primary_driver")
    if not source:
        return {
            "primary_driver": driver,
            "primary_driver_label": _driver_phrase(str(driver)) if driver else None,
            "rows": [],
            "evidence_id": None,
        }
    rows = ((source.get("value") or {}).get("rows")) or []
    ranked = sorted(rows, key=lambda r: abs(float(r.get("share_of_change") or 0)), reverse=True)
    return {
        "primary_driver": driver,
        "primary_driver_label": _driver_phrase(str(driver)) if driver else None,
        "evidence_id": source.get("evidence_id"),
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
        "Bu rapor ilişki dilindedir: birlikte görülen değişimleri söyler, nedenini iddia etmez.",
        "Grafikteki her sayı bu incelemede hesaplanan kanıttan gelir.",
    ]
    if (run.get("decision") or "") == "abstain" or (run.get("stop_reason") or "") == "abstain":
        notes.append("Değişim tek bir bölge veya kategoride toplanmadığı için tek kaynak işaretlenmedi.")
    if run.get("stop_reason") == "budget" or run.get("insufficient_kind") == "budget":
        notes.append("Araştırma bütçesi daha güçlü bir sonuca ulaşmadan doldu.")
    if run.get("insufficient_kind") == "multiple_plausible_drivers":
        notes.append("Birden fazla dilim eşik değerini aşıyor; tek kaynak seçilmedi.")
    cov = _first(evidence, "current_coverage")
    cov_val = (cov.get("value") or {}) if cov else {}
    if cov_val.get("truncated_current_period"):
        last = cov_val.get("current_last_observed")
        notes.append(f"Güncel dönem penceresi eksik olabilir (son gözlem: {last}).")
    if any(v.get("decision") == "reject" for v in reviews):
        notes.append("En az bir taslak iddia denetimden geçmedi ve yayımlanmadı.")
    return notes


def _recommended_next(run: dict[str, Any]) -> list[str]:
    items: list[str] = []
    driver = run.get("primary_driver")
    if driver and str(driver).strip().upper() == "AOV":
        items.append("Sepet tutarındaki düşüş hangi dilimde yoğunlaşıyor?")
    elif driver:
        items.append(f"{_driver_phrase(str(driver))} dilimini tek başına incele.")
    vol = _volume_value(run)
    volume = vol.get("volume_change_pct")
    if volume is not None and float(volume) < 0:
        items.append("Sipariş sayısındaki düşüş hangi dilimde toplanıyor?")
    if run.get("scope"):
        items.append("Tüm tabloya geri dön.")
    if (run.get("decision") or "") == "abstain":
        items.append("Hangi bölge öne çıkıyor?")
        items.append("Hangi kategori öne çıkıyor?")
    if not items:
        items.append("Detaylı raporu aç.")
    return items[:6]


def _kpis(run: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    change = _change_pct(run)
    vol = _volume_value(run)
    cmp = _first(evidence, "compare_periods")
    period = (cmp or {}).get("period") or {}
    inspect = _first(evidence, "inspect_dataset")
    n_rows = ((inspect or {}).get("value") or {}).get("n_rows")
    decision = run.get("decision") or "abstain"
    driver = run.get("primary_driver")
    if decision == "primary_driver" and driver:
        concentration = _driver_phrase(str(driver))
    elif decision == "value_not_volume":
        concentration = "Sepet tutarı, sipariş sayısı değil"
    elif decision == "ranking" and driver:
        concentration = _driver_phrase(str(driver))
    elif decision == "data_artefact":
        concentration = "Eksik veri penceresi olabilir"
    elif decision == "association":
        concentration = "İlişki var; neden değil"
    else:
        concentration = "Tek bir dilimde toplanmadı"
    metric = str(((cmp or {}).get("value") or {}).get("metric") or "").lower()
    return {
        "change_pct": change,
        "volume_change_pct": vol.get("volume_change_pct"),
        "aov_change_pct": vol.get("aov_change_pct"),
        "concentration": concentration,
        "previous_period": _period_label(period.get("previous")),
        "current_period": _period_label(period.get("current")),
        "n_rows": n_rows,
        "metric_noun": "Ücretler" if "fare" in metric else "Satışlar",
        "verdict": DECISION_LABELS.get(decision, decision),
    }


def _slice_table(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source = _best_segment(evidence)
    if not source:
        return []
    dims = list(((source.get("filters") or {}).get("dimensions")) or [])
    rows = list(((source.get("value") or {}).get("rows")) or [])
    ranked = sorted(rows, key=lambda r: abs(float(r.get("share_of_change") or r.get("change") or 0)), reverse=True)
    out: list[dict[str, Any]] = []
    for row in ranked[:8]:
        if dims:
            label = " × ".join(str(row.get(d, "")).strip() for d in dims if row.get(d) not in (None, ""))
        else:
            label = " · ".join(
                str(v)
                for k, v in row.items()
                if k not in {"previous", "current", "change", "share_of_change"} and v not in (None, "")
            )
        share = row.get("share_of_change")
        share_pct = None
        if share is not None:
            mag = abs(float(share))
            share_pct = round(mag * 100.0, 2) if mag <= 1.5 else round(mag, 2)
        out.append(
            {
                "label": label or "—",
                "previous": row.get("previous"),
                "current": row.get("current"),
                "change": row.get("change"),
                "share_pct": share_pct,
            }
        )
    return out


def _best_segment(evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    two = None
    one = None
    for ev in evidence:
        if ev.get("operation") != "segment_by":
            continue
        dims = ((ev.get("filters") or {}).get("dimensions")) or []
        rows = ((ev.get("value") or {}).get("rows")) or []
        if not rows:
            continue
        if len(dims) >= 2:
            two = ev
        elif one is None:
            one = ev
    return two or one


def _period_label(window: Any) -> str | None:
    if not isinstance(window, dict):
        return None
    start, end = window.get("start"), window.get("end")
    if start and end and start != end:
        return f"{start} — {end}"
    return start or end


def _first(evidence: list[dict[str, Any]], operation: str) -> dict[str, Any] | None:
    for ev in evidence:
        if ev.get("operation") == operation:
            return ev
    return None
