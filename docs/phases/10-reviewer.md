# Aşama 10.1 — Evidence Reviewer (V2 dilimi)

**Proje:** Evidra  
**Önceki:** [09-olist.md](09-olist.md), [10-v2.md](10-v2.md)  
**Baseline:** `v1.0.0` (V1 core + Olist). Bu dilim `feature/v2-reviewer` üzerinde.

Tek Analysis Agent. Multi-agent diyagram **yok**. Reviewer yeni analist değildir.

---

## Amaç

V1 evidence kilidini silmeden, yayımlanan claim’ler için **açık denetim kararı** üretmek: mevcut gerçeklik destekliyor mu?

Reviewer yeni gerçeklik üretmez.

---

## CAN

- Claim ↔ evidence tutarlılığı (id varlık, sayı bağlama — V1 kilit ile)
- Nedensel dil / sahte güven tespiti
- Evidence coverage (factual claim’de boş veya sahte id)
- Strength / overclaim: bağlı evidence `strength` veya `decision` ile iddia hizası
- Abstention’ın yasal olup olmadığı
- Karar: `accept | reject | revise | abstain` + `reason` + `issues`

## CANNOT

- Yeni analiz, yeni tool, yeni evidence
- Evidence log’u değiştirmek veya silmek
- `call_tool` / `run_sql` / `test_hypothesis` / `create_chart`
- Kullanıcıya kilidi bypass eden “doğrudan cevap”
- Başka dataset’e bakmak, adaptive research, LLM’in kararı vermesi (bu dilimde)

---

## Graf

```text
… → stop → validate_claims → review_claims → report → END
```

Capability abstain yolu da `validate_claims` → `review_claims` geçer.

`review_claims` **tool çağırmaz.** Input: freeze edilmiş evidence snapshot, claim listesi, `decision`, `stop_reason`, traces (okuma).

Sıra: önce `validate_claim` (V1 kilit, gevşemez); sonra Reviewer. Validator silinmez.

---

## Girdi

Claim’de `strength` alanı **eklenmez**. Strength Evidence scorer’dadır.

```json
{
  "question": "…",
  "decision": "primary_driver | value_not_volume | ranking | association | data_artefact | abstain",
  "stop_reason": "strong_evidence | space_exhausted | budget | abstain",
  "claims": [
    {
      "claim_id": "cl-001",
      "text": "…",
      "kind": "association | ranking | quality | abstention",
      "evidence_ids": [],
      "provenance_ok": true
    }
  ],
  "evidence": [
    {
      "evidence_id": "ev-…",
      "operation": "…",
      "source_columns": [],
      "filters": {},
      "period": null,
      "value": {},
      "strength": "weak | moderate | strong | inconclusive"
    }
  ],
  "traces": [{ "tool": "…", "ok": true, "summary": "…" }]
}
```

---

## Çıktı

Evidence değişmez. Run’a `reviews` eklenir; yayımlanan `claims` yalnız accept (ve uygulanmış revise) sonrası.

```json
{
  "claim_id": "cl-001",
  "decision": "accept | reject | revise | abstain",
  "reason": "…",
  "issues": [],
  "recommended_strength": "weak | moderate | strong | inconclusive | null",
  "recommended_claim": null
}
```

| Karar | Anlam |
| --- | --- |
| `accept` | Kilit + Reviewer kuralları geçti |
| `reject` | Yayımlanmaz; log aynı |
| `revise` | Yalnızca metin/kind daraltması; **yeni sayı yok** |
| `abstain` | Yetersiz kanıt; abstention claim’i uygunsa yayımlanır |

`recommended_claim` yeni metrik içermez (ör. “associated with”).

**Overclaim (V2 değeri):** bağlı evidence `strength` `weak` / `inconclusive` iken “primary driver” veya eşdeğer kesin sürücü iddiası → `reject` veya `revise`. Pay / `decision` ile metin çelişirse aynı.

**Abstention metni:** nedensel fiil yok. “Cannot determine the cause” V1 kilit tarafından reddedilir; beklenen dil “insufficient evidence”.

**Budget:** `stop_reason: budget` + bağlı kısmi claim → `accept`; kanıtsız sürücü → `reject`.

---

## Deterministik vs LLM

Bu dilim **%100 kural tabanlı**. LLM Reviewer ayrı dilimdir (V2.2+): olsa bile yalnız `reason` cümlesi; karar kurallarda kalır.

---

## Dosyalar (implementation; henüz yok)

Yeni: `analysis/reviewer.py`, `ReviewVerdict` modeli, `tests/test_reviewer.py`, reviewer fixture JSON.

Değişir: `analysis/graph.py` (`review_claims` + state `reviews`); pipeline yayımlanan liste; API/UI `reviews` gösterir; eval V1 golden’ı şişirmez.

Değişmez: `V1_TOOLS`, kapalı template seti, append-only log, `validate_claim` semantiği, heuristic fallback, Olist assemble, Aşama 6 golden kapıları.

Reviewer **tool adı değildir.**

---

## Testler (koddan önce bu matris)

1. Valid number (−30% vs “declined by 30%”) → ACCEPT  
2. Unsupported number (42% vs −30) → REJECT  
3. Causal verb → REJECT  
4. Factual, boş `evidence_ids` → REJECT  
5. Abstention + `decision: abstain` → ACCEPT  
6. Weak evidence + primary-driver overclaim → REJECT veya REVISE  
7. Association metni + association_test → ACCEPT  
8. Unknown `evidence_id` → REJECT  
9. “89% confidence” → REJECT  
10. Budget + bağlı kısmi claim → ACCEPT; kanıtsız sürücü → REJECT  

Regresyon: Reviewer, yasal V1 claim’ini (clear_driver, AOV trap, ranking, artefact, Olist association) reject etmez. `pytest` + `python -m analysis.eval` + Olist rubrik yeşil. Efficiency fail değil.

---

## Görevler

- [x] Sözleşme kilit (bu dosya)
- [x] `v1.0.0` tag + `feature/v2-reviewer`
- [ ] Test fixture’ları (implementation’dan önce veya birlikte)
- [ ] Deterministik `reviewer.py` + `review_claims` düğümü
- [ ] V1 + Olist regresyon
- [ ] UI’da `reviews` (ince; ajan değil)

---

## Çıkış kriteri

Açık `reviews` alanı; kilit gevşememiş; sentetik / Superstore / Olist gerilememiş; tool/evidence üretilmemiş.

**Bitti sayılır:** Reviewer V2.1 yeşil. Simpson / efficiency / ikinci dataset / infra **sonraki** dilimler.

---

## Bilinçli olarak yok

Planner / Analyst / Statistician, `run_python`, log rewrite, LLM karar, adaptive research, UCI/NYC, Postgres, MLflow, OpenTelemetry, auth.
