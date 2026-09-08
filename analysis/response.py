"""Deterministic evidence-grounded chat response. Does not analyze or call tools."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from analysis.evidence.validator import _CAUSAL, _FAKE_CONFIDENCE, _numbers_supported, _walk_numbers
from analysis.report import build_investigation_report

FALLBACK = (
    "Bu incelemeden güvenilir bir sonuç çıkaramıyorum. "
    "Mevcut kanıtlar bu soruyu yeterince desteklemiyor."
)

_ENGINE_LEAK = re.compile(
    r"\b(associated|primary_driver|share_of_change|compare_periods|segment_by|"
    r"decompose_volume_value|value_not_volume)\b",
    re.I,
)
_COMMA_DEC = re.compile(r"(\d+),(\d+)")


class ResponseContract(BaseModel):
    answer: str
    key_findings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)


def compose_response(run: dict[str, Any]) -> ResponseContract:
    if run.get("error"):
        return ResponseContract(answer=f"İnceleme çalışmadı: {run['error']}")
    draft = _compose_unchecked(run)
    ok, _reasons = validate_response(draft, run)
    if ok:
        return draft
    return _fallback_contract(run)


def validate_response(contract: ResponseContract, run: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    evid_ids = {e.get("evidence_id") for e in (run.get("evidence") or []) if e.get("evidence_id")}
    for eid in contract.evidence_refs:
        if eid not in evid_ids:
            reasons.append("unknown_evidence_id")
            break
    blob = " ".join([contract.answer, *contract.key_findings, *contract.limitations])
    if _CAUSAL.search(blob):
        reasons.append("causal_language")
    if _FAKE_CONFIDENCE.search(blob):
        reasons.append("fake_confidence")
    if _ENGINE_LEAK.search(contract.answer):
        reasons.append("engine_jargon")
    pool_values = _numeric_pool(run)
    if not _numbers_supported(_normalize_decimals(blob), pool_values):
        reasons.append("unbound_number")
    if _contradicts_abstain(run, contract):
        reasons.append("limitation_contradiction")
    return (not reasons, reasons)


def _compose_unchecked(run: dict[str, Any]) -> ResponseContract:
    report = run.get("investigation_report") or build_investigation_report(run)
    accepted = _accepted_claims(run)
    refs: list[str] = []
    findings: list[str] = []
    parts: list[str] = []
    change = _change_pct(run)
    driver = run.get("primary_driver")
    share = _driver_share(run, driver)
    vol = _volume_value(run)
    decision = run.get("decision") or "abstain"

    if not _has_strong_finding(accepted, decision):
        parts.append(_abstain_lead(change))
        findings.append("Yoğunlaşmış bir sürücü desteklenmiyor.")
        refs.extend(_evidence_ids(run, {"compare_periods"}))
    elif decision == "primary_driver" and driver:
        if change is not None:
            parts.append(_change_sentence(change))
            findings.append(_change_sentence(change))
            refs.extend(_evidence_ids(run, {"compare_periods"}))
        loc = _driver_phrase(str(driver))
        share_pct = _share_as_percent(share)
        parts.append(f"Düşüşün en güçlü desteklenen sinyali {loc} segmentinden geliyor.")
        findings.append(f"Öne çıkan dilim: {loc}.")
        refs.extend(_evidence_ids(run, {"segment_by"}))
        extra: list[str] = []
        if share_pct is not None:
            extra.append(f"bu dilim toplam değişimin %{_fmt(share_pct)}'ini oluşturuyor")
            findings.append(f"Katkı payı %{_fmt(share_pct)}.")
        aov = vol.get("aov_change_pct")
        volume = vol.get("volume_change_pct")
        if aov is not None:
            extra.append(_aov_clause(float(aov)))
            refs.extend(_evidence_ids(run, {"decompose_volume_value"}))
        if extra:
            parts.append(_cap(" ve ".join(extra) + "."))
        if _volume_not_aov(change, volume if volume is None else float(volume), aov if aov is None else float(aov)):
            parts.append(
                "Bu nedenle mevcut verideki ana sinyal sepet büyüklüğündeki düşüşten çok "
                "satış hacmindeki daralmayla ilişkili görünüyor."
            )
            findings.append("Sinyal: hacim daralması, sepet küçülmesi değil.")
    elif decision == "value_not_volume":
        if change is not None:
            parts.append(_change_sentence(change))
            findings.append(_change_sentence(change))
        aov = vol.get("aov_change_pct")
        volume = vol.get("volume_change_pct")
        parts.append(
            "Bulgu sipariş hacminden çok ortalama sepet tutarı (AOV) ile ilişkili: "
            f"AOV {_signed_pct(None if aov is None else float(aov))}, "
            f"sipariş hacmi {_signed_pct(None if volume is None else float(volume))}."
        )
        findings.append("Yorum: AOV, sipariş hacmi değil.")
        refs.extend(_evidence_ids(run, {"decompose_volume_value", "compare_periods"}))
    elif decision == "data_artefact":
        if change is not None:
            parts.append(_change_sentence(change))
        parts.append(
            "Görünen değişim eksik veya kesilmiş bir güncel dönemle birlikte görülüyor; "
            "bunu veri kalitesi işareti olarak okumak gerekir."
        )
        findings.append("Kalite: kesilmiş güncel pencere.")
        refs.extend(_evidence_ids(run, {"current_coverage", "compare_periods"}))
    elif decision == "ranking" and driver:
        parts.append(f"Mevcut karşılaştırmada öne çıkan dilim {_driver_phrase(str(driver))}.")
        findings.append(f"Sıralama: {driver}.")
        refs.extend(_evidence_ids(run, {"segment_by"}))
    elif decision == "association":
        assoc = _association(run)
        r = assoc.get("r")
        n = assoc.get("n")
        if r is not None:
            parts.append(
                f"Teslimat gecikmesi (gün) ile review skoru ilişkili görünüyor "
                f"(r={_fmt(float(r))}, n={n}). Bu bir ilişki ifadesidir, nedensellik değil."
            )
            findings.append(f"İlişki: r={_fmt(float(r))}.")
        refs.extend(_evidence_ids(run, {"association_test", "join_assemble", "run_sql"}))
    else:
        text = _first_accepted_text(accepted)
        if change is not None:
            parts.append(_change_sentence(change))
        if text:
            parts.append(_soften_claim(text))
        refs.extend(_claim_evidence_ids(accepted))

    limitations = _limitations_tr(run, report, decision)
    if limitations:
        closing = limitations[0] if decision == "abstain" else _pick_limitation(limitations)
        if closing not in parts:
            parts.append(closing)
    answer = " ".join(p.strip() for p in parts if p and p.strip())
    return ResponseContract(
        answer=answer or FALLBACK,
        key_findings=findings[:6],
        evidence_refs=_uniq(refs),
        limitations=limitations,
        suggested_followups=["Detaylı raporu göster.", "Evidence listesini göster."],
    )


def _fallback_contract(run: dict[str, Any]) -> ResponseContract:
    report = run.get("investigation_report") or {}
    return ResponseContract(
        answer=FALLBACK,
        limitations=_limitations_tr(run, report, run.get("decision") or "abstain"),
        suggested_followups=["Detaylı raporu göster."],
    )


def _accepted_claims(run: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = {v.get("claim_id"): v for v in (run.get("reviews") or [])}
    out = []
    for claim in run.get("claims") or []:
        verdict = reviews.get(claim.get("claim_id"))
        if verdict and verdict.get("decision") == "reject":
            continue
        out.append(claim)
    return out


def _has_strong_finding(accepted: list[dict[str, Any]], decision: str) -> bool:
    factual = [c for c in accepted if c.get("kind") != "abstention"]
    if decision == "abstain":
        return False
    if not factual:
        return False
    return decision in {
        "primary_driver",
        "value_not_volume",
        "data_artefact",
        "ranking",
        "association",
    }


def _contradicts_abstain(run: dict[str, Any], contract: ResponseContract) -> bool:
    if (run.get("decision") or "") != "abstain" and run.get("stop_reason") != "abstain":
        return False
    return bool(re.search(r"en güçlü desteklenen sinyal", contract.answer, re.I))


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


def _association(run: dict[str, Any]) -> dict[str, Any]:
    for ev in run.get("evidence") or []:
        if ev.get("operation") == "association_test":
            return ev.get("value") or {}
    return {}


def _driver_share(run: dict[str, Any], driver: str | None) -> float | None:
    if not driver:
        return None
    labels = [p.strip() for p in re.split(r"\s*[×x]\s*", str(driver)) if p.strip()]
    best = None
    for ev in run.get("evidence") or []:
        if ev.get("operation") != "segment_by":
            continue
        for row in (ev.get("value") or {}).get("rows") or []:
            blob = " ".join(str(v) for v in row.values())
            if labels and not all(lab in blob for lab in labels):
                continue
            share = row.get("share_of_change")
            if share is None:
                continue
            mag = abs(float(share))
            if best is None or mag > abs(best):
                best = float(share)
    return best


def _share_as_percent(share: float | None) -> float | None:
    if share is None:
        return None
    mag = abs(share)
    if mag <= 1.5:
        return round(mag * 100.0, 2)
    return round(mag, 2)


def _evidence_ids(run: dict[str, Any], operations: set[str]) -> list[str]:
    return [
        ev["evidence_id"]
        for ev in (run.get("evidence") or [])
        if ev.get("operation") in operations and ev.get("evidence_id")
    ]


def _claim_evidence_ids(claims: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for claim in claims:
        for eid in claim.get("evidence_ids") or []:
            if eid not in ids:
                ids.append(eid)
    return ids


def _numeric_pool(run: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    extras: list[float] = []
    for ev in run.get("evidence") or []:
        values.append(ev.get("value"))
        raw: list[float] = []
        _walk_numbers(ev.get("value"), raw)
        for n in raw:
            extras.append(n)
            extras.append(abs(n))
            if 0 < abs(n) <= 1.5:
                extras.append(round(abs(n) * 100.0, 2))
                extras.append(round(n * 100.0, 2))
    for claim in run.get("claims") or []:
        values.append(claim.get("text"))
    values.append(extras)
    return values


def _normalize_decimals(text: str) -> str:
    return _COMMA_DEC.sub(r"\1.\2", text)


def _limitations_tr(run: dict[str, Any], report: dict[str, Any], decision: str) -> list[str]:
    notes: list[str] = []
    if decision == "abstain" or run.get("stop_reason") == "abstain":
        notes.append("Yoğunlaşmış bir sürücü bu incelemede desteklenmiyor.")
    notes.append(
        "Ancak bu veriden değişimin altında yatan nedeni kesin olarak belirlemek mümkün değil; "
        "ifade ilişki dilindedir."
    )
    if run.get("stop_reason") == "budget":
        notes.append("Araştırma bütçesi daha güçlü bir sonuca ulaşmadan doldu.")
    if run.get("insufficient_kind") == "multiple_plausible_drivers":
        notes.append("Birden fazla dilim sürücü eşiğini geçiyor.")
    for raw in report.get("limitations") or []:
        low = str(raw).lower()
        if "truncated" in low or "incomplete" in low:
            notes.append("Güncel dönem penceresi eksik olabilir.")
    return _uniq(notes)[:5]


def _pick_limitation(notes: list[str]) -> str:
    for n in notes:
        if "nedeni kesin" in n or "ilişki dilindedir" in n:
            return n
    return notes[-1]


def _abstain_lead(change: float | None) -> str:
    if change is None:
        return FALLBACK
    return f"{_change_sentence(change)} Yoğunlaşmış bir sürücü desteklenmiyor."


def _change_sentence(change: float) -> str:
    if change < 0:
        return f"Satışlar bu dönemde %{_fmt(abs(change))} azaldı."
    if change > 0:
        return f"Satışlar bu dönemde %{_fmt(change)} arttı."
    return "Satışlar bu dönemde belirgin değişmedi."


def _aov_clause(aov: float) -> str:
    if aov > 0:
        return f"ortalama sepet tutarı %{_fmt(aov)} arttı"
    if aov < 0:
        return f"ortalama sepet tutarı %{_fmt(abs(aov))} azaldı"
    return "ortalama sepet tutarı durağan"


def _volume_not_aov(change: float | None, volume: float | None, aov: float | None) -> bool:
    if change is None or volume is None or aov is None:
        return False
    if change >= 0:
        return False
    return abs(volume) > abs(aov) and volume < 0


def _driver_phrase(label: str) -> str:
    parts = [p.strip() for p in re.split(r"\s*[×x]\s*", label) if p.strip()]
    if len(parts) == 2:
        return f"{parts[0]} bölgesindeki {parts[1]}"
    return label


def _signed_pct(value: float | None) -> str:
    if value is None:
        return "bilinmiyor"
    if value < 0:
        return f"%{_fmt(abs(value))} azaldı"
    if value > 0:
        return f"%{_fmt(value)} arttı"
    return "%0 değişmedi"


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    n = float(value)
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    text = f"{n:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _soften_claim(text: str) -> str:
    out = re.sub(r"\bis associated with\b", "ile ilişkili görünüyor", text, flags=re.I)
    out = re.sub(r"\bassociated\b", "ilişkili", out, flags=re.I)
    return out


def _first_accepted_text(accepted: list[dict[str, Any]]) -> str:
    for claim in accepted:
        if claim.get("kind") != "abstention" and claim.get("text"):
            return str(claim["text"])
    return ""


def _cap(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
