# Aşama 3 — Evidence ve provenance

**Proje:** Evidra  
**Önceki:** [02-analysis-engine.md](02-analysis-engine.md)  
**Sonraki:** [04-tools-heuristic.md](04-tools-heuristic.md)

Engine dönüş tipi Evidence olur. UI/rapor süsü değildir.

---

## Amaç

[SCHEMAS.md](../SCHEMAS.md) içindeki Evidence ve Claim sözleşmesini kodda kilitlemek (Pydantic veya eşdeğeri). Claim validator: no evidence → no claim; nedensel fiil reddi; chart `evidence_ids`.

Strength scorer kural tabanlıdır; LLM strength yazmaz.

---

## Sözleşme (özet)

**Evidence:** `evidence_id`, `operation`, `source_columns`, `filters`, `period`, `value`, `strength` (`weak | moderate | strong | inconclusive`).

**Claim:** `claim_id`, `text`, `kind` (`association | ranking | quality | abstention`), `evidence_ids`, `provenance_ok`.

Olgusal claim (association, ranking, quality) boş `evidence_ids` ile yaşayamaz. Abstention, capability kesişimini gösteren evidence’a bağlanabilir.

**Validator**

- Evidence log’da olmayan id → fail / drop  
- Metindeki sayı evidence payload’da yok → drop veya rewrite (evidence kazanır)  
- Causal token’lar (`cause`, `because`, `root cause`, `sebep`, eşdeğer nedensel kalıplar) → reject  
- “89% confidence” veya strength dışı yüzde güven → reject  

Grafik nesnesi: Plotly JSON + `evidence_ids`. Grafik, sayı kaynağı değildir.

---

## Görevler

- [ ] Evidence / Claim modelleri
- [ ] Engine sarmalayıcı: her operasyon en az bir Evidence üretir
- [ ] Scorer: pay / ayrışma / kalite kuralları yazılı
- [ ] `test_no_evidence_no_claim`
- [ ] `test_causal_verb_rejected`
- [ ] Chart şemasında `evidence_ids` zorunlu
- [ ] Append-only: mevcut evidence mutasyonu yok

---

## Çıkış kriteri

Sahte rapor yolu (evidence’siz sayı veya nedensel cümle) testte **fail** eder. Meşru `compare_periods` çıktısı `provenance_ok` claim üretebilir.

**Bitti sayılır:** Validator fail-able; Aşama 4 tool’ları Evidence döndürür.

---

## Bilinçli olarak yok

LangGraph, LLM, FastAPI UI, Olist, `run_python`, 5 panel.
