# Aşama 1 — Sentetik fixture ve capability

**Proje:** Evidra  
**Önceki:** [00-sozlesme.md](00-sozlesme.md)  
**Sonraki:** [02-analysis-engine.md](02-analysis-engine.md)

İlk veri işi. LLM yok. Amaç: Superstore rolleri, capability sözlüğü ve **ölçülebilir** dört fixture.

Olist bu aşamada indirilmez. Büyük CSV commit edilmez.

---

## Amaç

1. Superstore kolonlarını *elle* tanımak; **rolleri** isme hardcode etmeden tanımlamak.  
2. [SCHEMAS.md](../SCHEMAS.md) capability sözlüğünü Superstore + sentetik şemaya bağlamak.  
3. Dört sentetik fixture yazmak; her birinin beklenen kararı (`expected.json`) tartışmasız olsun.

---

## Superstore roller (hedef)

Tipik eşleme (kaynak kolon adıyla güncellenir):

| Rol | Örnek semantik |
| --- | --- |
| `time` | sipariş tarihi |
| `metric` | sales, profit, quantity, discount |
| `dimension` | region, state, category, sub-category, segment |
| `id` | order id, customer id |
| `ignore` | analiz dışı |

Taslak: `configs/schema_roles.yml` veya markdown tablosu. Aşama 2 kodu bunu okur.

Capability Superstore’da beklenenler (tek tablo): `temporal_analysis`, `segmentation`, `metric_comparison`, `volume_value_decomposition` (order/customer id varsa), `interaction`, `anomaly_detection`, `association`. `causal_analysis` = false. `multi_table_join`, `delivery_analysis`, `retention_analysis` = false → bu sorularda **abstain**.

---

## Dört fixture

Küçük satış tabloları; Superstore’a *benzer roller* (aynı motor). Zorunlu roller: tarih, bölge, ürün/kategori, satış, sipariş veya müşteri id.

| Fixture | Gömülü gerçek | Beklenen karar |
| --- | --- | --- |
| `clear_driver` | Son dönemde toplam satış düşer; asıl pay **tek bölge × tek kategori** | Birincil sürücü cümlesi (ör. `West × Office Supplies`) + evidence |
| `aov_trap` | Hacim (müşteri/sipariş) az değişir; AOV belirgin düşer (veya tersi, net yazılır) | Volume vs value ayrımı; hacmi “sürücü” ilan etmek **fail** |
| `no_signal` | Dönemler arası metrik düz / gürültü bandında; tek sürücü yok | **Abstain** veya `inconclusive`; uydurma sürücü **fail** |
| `missingness` | Görünür düşüş eksik kayıt / kesik pencere artefact’ı | `data_artefact` / quality; iş sürücüsü iddia etme |

Simpson, outlier-as-driver, korelasyon-tuzağı **bu aşamada yok** (backlog).

Dosyalar (küçük olanlar repo):

- `data/fixtures/clear_driver.csv` + `.expected.json`
- `data/fixtures/aov_trap.csv` + `.expected.json`
- `data/fixtures/no_signal.csv` + `.expected.json`
- `data/fixtures/missingness.csv` + `.expected.json`

`expected.json`: dönem tanımı, sürücü veya `abstain`, kaba yüzde bantları, yasak claim türü.

Superstore: `data/raw/` + gitignore. `data/README.md`: kaynak, lisans, indirme.

---

## Görevler

- [ ] Superstore yerel; lisans/kaynak notu
- [ ] Satır/kolon, tip, eksik, duplicate özeti
- [ ] Kolon → rol tablosu
- [ ] Capability sözlüğü Superstore + sentetik için doldurulmuş
- [ ] Dört CSV, sabit seed, tekrar üretilebilir
- [ ] Dört `expected.json`
- [ ] Eval aday maddeleri bu fixture’lara bağlanmış (tam matris Aşama 6)

---

## Çıkış kriteri

- Superstore rol tablosu dolu.  
- Dört kırık/karar, dosyayı açmadan tarif edilebilir.  
- Teslimat sorusu Superstore’da capability kesişimi boş — beklenen abstain yazılı.

**Bitti sayılır:** Fixture + contract var; Aşama 2 bunları girdi alır.

---

## Bilinçli olarak yok

Pandas pipeline ürünü, ajan, Olist, UI, LangGraph, eval runner.
