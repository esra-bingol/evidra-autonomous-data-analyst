# Aşama 2 — Analysis engine (LLM yok)

**Proje:** Evidra  
**Önceki:** [01-synthetic-capability.md](01-synthetic-capability.md)  
**Sonraki:** [03-evidence-provenance.md](03-evidence-provenance.md)

İlk uygulama kodu. Computation layer. LLM `df.groupby` yazdırmaz.

---

## Amaç

Dataset’i **fonksiyonlarla** analiz eden katman. Çıktılar Aşama 3’te Evidence nesnesine sarılır; bu yüzden ham sonuçta `operation`, `source_columns`, `filters`, `period` **kaybolmaz** (dict/dataclass şimdiden taşıyabilir).

Hedef paket (isimler esnek, sorumluluklar değil):

```text
analysis/
  profiler.py
  quality.py
  capabilities.py
  periods.py
  segments.py
  volume_value.py
  statistics.py
  anomalies.py
  visualization.py
```

Dosyalar iş oldukça açılır; boş klasör ormanı yok.

---

## Yetenekler

| Fonksiyon | İş |
| --- | --- |
| `profile_dataset` | satır/kolon, tipler, örnek, rol tahmini |
| `detect_missing_values` / `detect_duplicates` | kalite |
| `quality_score` | 0–100, kuralı yazılı |
| `detect_capabilities` | SCHEMAS flag’leri; `causal_analysis` her zaman false |
| `compare_periods` | previous / current / change |
| `segment_by` | bir veya iki boyut |
| `decompose_volume_value` | hacim vs AOV/değer |
| `detect_anomalies` | IQR / z / zaman sapması; ML yok |
| `association_test` | istatistik + p; **cause yok** |
| `create_visualization` | Plotly JSON; sonra `evidence_ids` bağlanır |

Dönem: `time` kolonundan son tam dönem vs önceki (ay varsayılan; veri kısaysa hafta). Hardcode yıl yok.

---

## Görevler

- [x] Superstore + dört fixture aynı API (`load_tabular`)
- [x] Profiler + kalite + `detect_capabilities`
- [x] `compare_periods` / `segment_by` / `decompose_volume_value` fixture beklentileriyle yön tutar
- [x] İki boyutlu kırılım (`clear_driver` etkileşimi)
- [x] `no_signal` ve `missingness` için “sahte sürücü üretmeme” spot-check
- [x] En az 2 grafik JSON (henüz UI yok)
- [x] pytest: `clear_driver` sürücü eşleşmesi engine seviyesinde

---

## Çıkış kriteri

Ajan yokken script (veya eşdeğeri) `clear_driver` birincil sürücüsünü doğru basar. Superstore’da dönem + bölge kırılımı çalışır. Capability fonksiyonu teslimat flag’ini Superstore’da false döner.

**Bitti sayılır:** Test yeşil; provenance alanları sonuçta duruyor (Aşama 3 sarmalayacak).

---

## Bilinçli olarak yok

FastAPI, LangGraph, tool calling, Pydantic Claim, sandbox, UI, Olist join, `run_python`.
