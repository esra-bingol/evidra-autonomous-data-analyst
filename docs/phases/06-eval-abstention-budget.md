# Aşama 6 — Eval, abstention, budget

**Proje:** Evidra  
**Önceki:** [05-investigation-policy.md](05-investigation-policy.md)  
**Sonraki:** [07-minimal-ui.md](07-minimal-ui.md)

**V1 CORE KAPISI.** UI zorunlu değil. Bundan sonra Olist’e (Aşama 9) geçilmez; önce bu kapı yeşil, UI isteğe bağlı Aşama 7.

---

## Amaç

Ajanı ~20 maddelik bir **matris** ile ölçmek (20×5 cartesian değil). Abstention ve budget’ın ürün davranışı olduğunu kanıtlamak. Efficiency log’lanır, gate değildir.

---

## Matris (~20)

| Adet | `metric_type` |
| --- | ---: |
| 5 | driver |
| 3 | trap (AOV vb.) |
| 3 | abstain |
| 3 | interaction |
| 2 | temporal |
| 2 | anomaly |
| 2 | numerical |

EvalItem şeması: [SCHEMAS.md](../SCHEMAS.md) §7.

Abstain örnekleri: teslimat sorusu + Superstore; `no_signal`; capability’siz ilişki/retention.

Simpson / outlier / korelasyon-tuzağı madde **yok** (backlog).

---

## Gates (V1)

| Gate | Anlam |
| --- | --- |
| Correctness | Sayı, sürücü, sıralama; tolerans (ör. %0.5) |
| Evidence | Kanıtsız claim yok; coverage |
| Completeness | Geçerli `stop_reason` ile loop biter |
| Forbidden language | Causal fiil / sahte güven yok |

`efficiency_log`: tool sayısı, süre, token — **kapı değil**.

Hallüsinasyon: evidence dışı sayı enjekte eden yol fail.

Koşu: `pytest` ve/veya CLI; JSON skor özeti. `POST /eval` varsa aynı core’u çağırır.

Budget: en az bir testte limitin durduğu ve validator’ın kısmi evidence ile çalıştığı görülür.

---

## Görevler

- [x] Golden JSON (~20) + runner
- [x] Dört fixture + Superstore ranking/numeric
- [x] Abstain maddeleri yeşil
- [x] Budget stop testi
- [x] Efficiency log dosyası/alanı (gate değil)
- [x] README: eval nasıl koşulur (Aşama 6 bitince)

---

## Çıkış kriteri — V1 core bitti

- Sentetik sürücü / tuzak / abstain matris kapıları yeşil (heuristic zorunlu; LLM opsiyonel bayrak).  
- Kanıt kilidi ve yasak dil yakalanır.  
- Superstore ranking/numeric maddelerinin çoğu doğru.  
- UI yoktur veya yok sayılır; core CLI/API yeter.

Portföyde **V1 core**: Superstore + sentetik üzerinde savunan, ölçülebilir investigation engine. Demo yıldızı henüz Olist değil.

**Bitti sayılır:** Eval raporu tekrar üretilebilir; Aşama 7 (UI) veya 9 (Olist, UI atlanarak yalnızca core üzerinden) bilinçli seçilir — Olist yine 9. aşama iş emrine tabidir.

---

## Bilinçli olarak yok

Minimal UI zorunluluğu, MLflow, Olist rubrik seti, Reviewer ajanı, `run_python`, efficiency gate.
