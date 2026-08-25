# Aşama 4 — Tool yüzeyi ve heuristic investigator

**Proje:** Evidra  
**Önceki:** [03-evidence-provenance.md](03-evidence-provenance.md)  
**Sonraki:** [05-investigation-policy.md](05-investigation-policy.md)

Engine + evidence’ı ajanın çağıracağı tool’lara çevir. Heuristic, Aşama 5 grafının **aynı** iskeletini kullanır; ayrı “Superstore raporu” yazmaz.

---

## Amaç

JSON-serializable tool I/O (Pydantic). LLM yok. Policy = heuristic: kapalı template’leri rank/bind/skip, budget’a yaz, abstain et.

V1 tool listesi: [SCHEMAS.md](../SCHEMAS.md) §6. `run_python` yok.

---

## Heuristic = aynı graf

```text
inspect → profile → detect_capabilities → intersect
       → rank_hypotheses → experiment_loop → score
       → stop → validate_claims → report
```

Düz Python orkestrasyonu yeter; LangGraph paketi Aşama 5.

- `no_signal` fixture → sürücü uydurma; `stop_reason: abstain` veya `inconclusive` + abstention/quality claim.  
- Superstore + teslimat sorusu → `delivery_analysis` yok → **abstain**, hipotez yok.  
- `budget` RunState’te: `max_hypotheses` 8, `max_experiments` 20, `max_interaction_depth` 2, `max_seconds`.

---

## Görevler

- [ ] Her tool için I/O şeması; çıktı Evidence veya Evidence üreten wrapper
- [ ] DuckDB: tek tablo register; yalnızca SELECT
- [ ] Heuristic investigator dört fixture + Superstore abstain örneği
- [ ] Structured log: ad, süre, başarı, özet
- [ ] Budget aşıldığında `stop_reason: budget`, crash yok
- [ ] Hata mesajları: boş kolon, eksik tarih, tek dönem

---

## Çıkış kriteri

LLM kapalı. “Satış neden değişti?” + `clear_driver` → plan + evidence + doğru sürücü (association dili). `no_signal` ve teslimat/Superstore abstain. Tool log izlenebilir.

**Bitti sayılır:** Heuristic graf Aşama 5’e taşınabilir; sürücü ve abstain testleri yeşil.

---

## Bilinçli olarak yok

OpenAI/Anthropic zorunluluğu, LangGraph (Aşama 5), React, Olist, `run_python`.
