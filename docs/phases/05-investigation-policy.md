# Aşama 5 — Investigation policy (LangGraph)

**Proje:** Evidra  
**Önceki:** [04-tools-heuristic.md](04-tools-heuristic.md)  
**Sonraki:** [06-eval-abstention-budget.md](06-eval-abstention-budget.md)

LangGraph burada başlar. Serbest ReAct yok. LLM varsa yalnızca **kapalı template seçimi** (rank/bind/skip); source of truth değildir.

---

## Amaç

Aşama 4 heuristic grafını LangGraph düğümlerine taşımak. LLM açık/kapalı **aynı** sürücü ve abstain davranışını korur. Allowlist dışı `template_id` fail eder.

---

## Zorunlu graf

```text
START
  → inspect
  → profile
  → detect_capabilities
  → intersect          (boş → abstain → validate_claims → report → END)
  → rank_hypotheses    (heuristic veya LLM; kapalı set)
  → experiment_loop
  → score
  → stop               (strong_evidence | space_exhausted | budget)
  → validate_claims
  → report
END
```

State: [SCHEMAS.md](../SCHEMAS.md) RunState.

LLM bağlama:

- Anahtar yok → heuristic, sessiz fallback  
- Anahtar var → structured output yalnızca template id + bindings (rol tablosundaki kolonlar)  
- Model yeni `template_id` üretir → **fail testi**  
- Model rakamı evidence ile çelişirse evidence kazanır  

---

## Görevler

- [x] LangGraph state + düğümler (yukarıdaki sıra)
- [x] `rank_hypotheses` kapalı set; LLM allowlist
- [x] `test_unknown_template_fails`
- [x] Sentetik: LLM açık/kapalı aynı `clear_driver` sürücüsü
- [x] Intent `ranking`: hipotez döngüsü kısalır; yine evidence zorunlu
- [x] Budget düğümü stop_reason yazar

---

## Çıkış kriteri

Plan adımları izlenebilir. Birincil sürücü + evidence. Nedensel cümle validator’da yok. Allowlist ihlali testte fail.

**Bitti sayılır:** İki yol (heuristic / LLM) aynı sürücü ve abstain; Aşama 6 eval’e hazır.

---

## Bilinçli olarak yok

Ayrı Reviewer ajanı, `run_python`, production UI, Olist, eval matrisinin tamamı (Aşama 6).
