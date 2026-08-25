# Data

Sıra (değişmez): **sentetik golden → Superstore → Olist**.

Engine, eval ve “doğru sürücü” **sentetikte** kanıtlanır. Superstore ilk gerçek dünya / tek tablo benchmark’ıdır. Olist Aşama 9.

| Set | GitHub commit | Disk |
| --- | --- | --- |
| Sentetik fixture (`data/fixtures/`) | Evet | Evet — ilk iş |
| Superstore | Hayır | İndirip `data/raw/superstore.csv` tutulabilir |
| Olist | Hayır | Aşama 9’a kadar gerekmez |

Sentetik dosyayı `data/raw/superstore.csv` diye adlandırma. Ham Superstore yalnızca `raw/` altındadır.

`processed/` ihtiyaç olunca açılır (temizlenmiş Superstore). Boş `raw/` + `processed/` açmak Aşama 1 sayılmaz.

---

## Sentetik golden (commit edilir)

Üretim (sabit seed):

```bash
python data/generate_fixtures.py
```

| Dosya | Gömülü gerçek | Beklenen karar |
| --- | --- | --- |
| `fixtures/clear_driver.csv` | Son ay satış düşer; pay **West × Office Supplies** | Birincil sürücü o etkileşim |
| `fixtures/aov_trap.csv` | Sipariş sayısı az değişir; AOV düşer | Sürücü değer/AOV; hacim iddiası fail |
| `fixtures/no_signal.csv` | Dönemler gürültü bandında | `abstain` / `inconclusive` |
| `fixtures/missingness.csv` | Görünür düşüş kesik kayıt penceresi | `data_artefact`; iş sürücüsü yok |

Her CSV için `*.expected.json` vardır.

Kolon rolleri (dört fixture ortak):

| Kolon | Rol | Semantic |
| --- | --- | --- |
| `order_id` | `id` | order |
| `customer_id` | `id` | customer |
| `order_date` | `time` | order_date |
| `region` | `dimension` | region |
| `category` | `dimension` | product |
| `sales` | `metric` | sales |
| `quantity` | `metric` | quantity |

Capabilities (sentetik + Superstore tek tablo): `temporal_analysis`, `segmentation`, `metric_comparison`, `volume_value_decomposition`, `interaction`, `anomaly_detection`, `association`. `causal_analysis` false. `multi_table_join`, `delivery_analysis`, `retention_analysis` false — teslimat sorusunda abstain.

---

## Superstore (commit edilmez)

Kaynak (Tableau Sample Superstore): [Sample Data](https://public.tableau.com/app/learn/sample-data) — Superstore Sales (xls).

Kaggle kopyası (CSV, aynı örnek veri): [vivek468/superstore-dataset-final](https://www.kaggle.com/datasets/vivek468/superstore-dataset-final).

Yerel yol: `data/raw/superstore.csv` (xls ise CSV’ye çevir, bu adla koy). **Push etme.** Lisans/kullanım: Tableau örnek veri; eğitim. Kaggle sayfasındaki notu da oku.

Bu kopya: `latin-1`, 9994 satır, 21 kolon, `Order Date` `MM/DD/YYYY`, 2014-01-03 … 2017-12-30. Rol tablosu: `configs/schema_roles.yml`. Engine isme hardcode etmez.

Engine **önce** fixture’larda yeşil olur; Superstore ikinci sıradır.

---

## Olist

Aşama 9. Şimdi indirme.
