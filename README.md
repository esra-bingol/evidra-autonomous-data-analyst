# Evidra

**Kanıta bağlı, otonom veri inceleme motoru**

Depo: `evidra-autonomous-data-analyst`

Evidra, bir CSV veya Excel tablosu üzerindeki iş sorusunu sohbet cevabına çeviren bir chatbot değildir. Soru bir araştırma problemi olarak ele alınır: kolon rolleri çıkarılır, yetenekler soruyla kesiştirilir, kapalı hipotez şablonları test edilir, her sayı bir kanıt nesnesine bağlanır ve bağlanamayan cümle yayımlanmaz.

<!-- Görsel: ürün logosu veya genel bakış karesi -->
<!-- ![Evidra genel bakış](docs/screenshots/04-dashboard.png) -->

---

## Overview

Bir metrik değiştiğinde (“satış neden düştü?”) birkaç yapısal açıklama mümkündür: sipariş sayısı mı daraldı, sepet tutarı mı küçüldü, tek bir bölge/kategori mi çekti, yoksa güncel dönem penceresi mi eksik? Bunlardan birini, kayıtlı bir deney çalıştırmadan adlandırmak inceleme değil, hikâye üretmektir.

Evidra bu yolu görünür ve denetlenebilir kılar:

```text
SORU → YETENEKLER → HİPOTEZLER → DENEYLER
     → KANIT → KARAR → bütçe / dur
     → İDDİA DOĞRULAYICI → YAYIMLANAN CEVAP
```

Dil modeli (veya deterministik politika) **ne bakılacağına** karar verir. Hesaplayan katman Python, SQL ve istatistiktir. Motorun dönüş tipi kanıttır. Model, gerçeğin kaynağı değildir.

V1 rapor dili **ilişki** dilidir, nedensellik değil. Güç `weak | moderate | strong | inconclusive` olarak tutulur; uydurma bir “%89 güven” üretilmez.

---

## Key Features

- **Kapalı deney uzayı:** Motor yeni operatör icat etmez. Şablonlar sabitir: dönem karşılaştırması, dilim, hacim–sepet ayrıştırması, etkileşim, anomali, ilişki testi.
- **Yetenek ∩ soru:** Gerekli kolon yoksa (ör. teslimat gecikmesi, müşteri kaybı) hipotez uydurulmaz; açıkça çekimser kalınır.
- **Kanıt nesnesi:** Her işlem `operation`, kolonlar, filtre, dönem, değer ve güç ile kayıt altına alınır. Cümlede geçen her sayı bu kayıttan gelir.
- **İddia doğrulayıcı + reviewer:** Nedensel fiiller, bağlanmamış sayılar ve motor jargonu yayımlanmaz.
- **Araştırma bütçesi:** Hipotez sayısı, deney sayısı, etkileşim derinliği ve duvar saati dolunca durulur; anlatı tamamlanana kadar dönülmez.
- **Soru tipine göre cevap:** “Neden değişti?” ile “hangi kategori öne çıkıyor?” aynı abstain cümlesine düşmez; ranking sorusu ilgili kırılımı önce test eder.
- **Çok yüzeyli ürün:** Genel bakış, analiz sohbeti, inceleme konsolu ve detaylı rapor aynı inceleme grafiğinden beslenir.
- **Takip soruları:** “Peki West’te durum nasıl?” donmuş kanıttan cevaplanır. “West’i ayrı incele” aynı sohbette kapsamlı (scoped) bir run başlatır.
- **Değerlendirme kapısı:** Sentetik golden set, adversarial tablolar, ürün soruları ve efficiency overlay. Doğruluk ve yasaklı dil release kapısıdır; gecikme sayısı değildir.

---

## Project Structure

```text
evidra-autonomous-data-analyst/
├── analysis/                     # İnceleme motoru ve API
│   ├── api.py                    # FastAPI: dataset, chat, run, sayfalar
│   ├── graph.py                  # LangGraph: inspect → rank → experiment → report
│   ├── heuristic.py              # Kapalı şablon sıralama ve deney döngüsü
│   ├── policy.py                 # Intent (why_change / ranking / association)
│   ├── router.py                 # Sohbet turu: incele / kanıttan cevapla / abstain
│   ├── response.py               # Donmuş run’dan Türkçe analist cevabı
│   ├── report.py                 # Analist brifingi + KPI + dilim tablosu
│   ├── charts.py                 # Soru ve kanıta göre Plotly seçimi
│   ├── chat.py                   # Sohbet katmanı (SQL/Python çalıştırmaz)
│   ├── scope.py                  # Follow-up dilim filtresi
│   ├── evidence/                 # Kanıt modeli, skor, doğrulayıcı
│   ├── tools/                    # Kayıtlı araçlar (DuckDB, runtime)
│   └── eval/                     # Golden, adversarial, product, efficiency
├── ui/                           # Ürün yüzeyleri (vanilla HTML/CSS/JS)
│   ├── dashboard.html            # Genel bakış
│   ├── chat.html                 # Analiz sohbeti
│   ├── index.html                # İnceleme konsolu
│   └── report.html               # Detaylı rapor
├── data/
│   ├── fixtures/                 # Sentetik ve şema fixture’ları (commit’li)
│   ├── raw/                      # Superstore / Olist / UCI (yerel, commit edilmez)
│   └── processed/runs/           # Tamamlanmış inceleme kayıtları
├── evals/                        # Golden, adversarial, product, rubric JSON
├── tests/                        # pytest
├── docs/                         # Mimari, şemalar, fazlar, demo
│   └── screenshots/              # Portfolio kareleri (PNG’leri sen eklersin)
├── PLAN.md
├── pyproject.toml
└── README.md
```

---

## Installation & Setup

### 1. Önkoşullar

- Python **3.11+**
- [uv](https://docs.astral.sh/uv/) (kilit dosyası: `uv.lock`)

### 2. Bağımlılıklar

```bash
uv sync --extra dev
```

Çekirdek paketler: pandas, numpy, scipy, plotly, openpyxl, pydantic, duckdb, langgraph, fastapi, uvicorn. Geliştirme: pytest, httpx.

### 3. Çalıştır

```bash
uv run python -m analysis.api
```

Yerel, kimlik doğrulama yok. Port **8765**.

- Genel bakış: `http://127.0.0.1:8765/dashboard`
- Analiz sohbeti: `http://127.0.0.1:8765/chat`
- İnceleme konsolu: `http://127.0.0.1:8765/console`
- Detaylı rapor: `http://127.0.0.1:8765/report?run={id}`

Hızlı sahne: `http://127.0.0.1:8765/chat?fixture=clear_driver`

---

## Usage Guide

### Ürün yüzeyleri

**Genel bakış (`/dashboard`)**  
Son incelemenin KPI’ları, kanıttan üretilen grafikler, sıralanabilir dilim tablosu, geçmiş raporlar ve sistem özeti. Landing metni değil, analist ana ekranı.

<!-- ![Genel bakış](docs/screenshots/04-dashboard.png) -->

**Analiz sohbeti (`/chat`)**  
Veri setini bağla (örnek fixture veya CSV/Excel), iş sorusunu sor. Cevap Türkçe analist dilindedir: önceki → güncel tutar, yoğunlaşan dilim, hacim/sepet okuması. Sağ panelde akış, KPI ve grafik; mesajda zaman ve durum satırı vardır.

<!-- ![Sohbet soru ve cevap](docs/screenshots/01-chat-question.png) -->
<!-- ![Sohbet sağ panel](docs/screenshots/02-chat-preview.png) -->

**İnceleme konsolu (`/console`)**  
Dört adım: veri seti → iş sorusu → nasıl bakıldı → sonuç (KPI, grafik, dilim tablosu). Araç izi, kanıt ID’leri ve denetim kayıtları katlanabilir teknik bölümdedir.

**Detaylı rapor (`/report`)**  
Sohbetteki özetin aynısı, KPI şeridi, grafikler, headline bulgular, sonraki sorular, dilim tablosu ve “bu raporun söylemediği şey”. Motor jargonu ekte kalır.

<!-- ![İnceleme raporu](docs/screenshots/03-report.png) -->

### Örnek sorular

| Veri | Soru | Beklenen davranış |
| --- | --- | --- |
| Net yoğunlaşma (`clear_driver`) | Satış neden değişti? | West × Office Supplies; tutar ve pay |
| Aynı run follow-up | Hangi kategori öne çıkıyor? | Ranking: kategori kırılımı |
| Aynı run follow-up | West bölgesindeki Office Supplies neden düştü? | Scoped run, yeni inceleme |
| AOV tuzağı (`aov_trap`) | Satış neden değişti? | Sepet tutarı, sipariş sayısı değil |
| Sinyal yok (`no_signal`) | Satış neden değişti? | Abstain; tek kaynak işaretlenmez |
| Taksi (`taxi_trips`) | Ücret neden değişti? | “Satışlar” demez; ücret dili |
| Superstore (yerel) | Hangi bölge öne çıkıyor? | Ranking; önce Region |
| Teslimat / churn | Teslimat gecikmesi puanı nasıl etkiler? | Capability yoksa abstain |

<!-- ![Çekimser cevap](docs/screenshots/05-abstain.png) -->

### CLI inceleme

API olmadan aynı grafiği çalıştırmak için:

```bash
uv run python -m analysis.graph \
  --data data/fixtures/clear_driver.csv \
  --question "Satış neden değişti?"
```

Olist (çok tablo, `data/raw/` yerelde olmalı):

```bash
uv run python -m analysis.graph \
  --data data/raw \
  --question "Teslimat gecikmesi ile review score arasında association var mı?"
```

### Değerlendirme

```bash
uv run python -m analysis.eval
uv run pytest
```

Alt süitler:

```bash
uv run python -m analysis.eval.efficiency
uv run python -m analysis.eval.adaptive
```

Golden matris: `evals/golden.json` (~20 madde: sürücü, tuzak, abstain, etkileşim, zamansal, anomali, sayısal, bütçe). Kapılar: sayısal doğruluk, kanıt bağlama, `stop_reason` bütünlüğü, yasaklı dil. Araç sayısı ve gecikme `evals/out/efficiency_log.jsonl` dosyasına yazılır; release kapısı değildir.

---

## Data & Fixtures

| Fixture | Dosya | Ne için |
| --- | --- | --- |
| `clear_driver` | `data/fixtures/clear_driver.csv` | Tek dilimde net yoğunlaşma |
| `aov_trap` | `data/fixtures/aov_trap.csv` | Hacim sabit, sepet düşer |
| `no_signal` | `data/fixtures/no_signal.csv` | Yayılmış değişim; abstain |
| `missingness` | `data/fixtures/missingness.csv` | Eksik / kesilmiş pencere |
| `taxi_trips` | `data/fixtures/taxi_trips.csv` | Coğrafya + zaman; ücret metriği |
| `superstore` | `data/raw/superstore.csv` | Tek tablo genelleme (yerel) |
| `olist` | `data/raw/` | Çok tablo (yerel, commit edilmez) |
| `uci_retail` | `data/fixtures/retail_line_items.csv` | Satır kalemi şema adaptörü |

Yükleme (yalnız HTTP multipart, fixture/CLI değil): varsayılan 10 MiB, 50_000 satır, 64 kolon. Aşım **413**, biçim hatası **400**. Ortam değişkenleri: `EVIDRA_MAX_UPLOAD_BYTES`, `EVIDRA_MAX_UPLOAD_ROWS`, `EVIDRA_MAX_UPLOAD_COLUMNS`, `EVIDRA_MAX_UPLOAD_CELL_LENGTH`.

Kalıcı run’lar `data/processed/runs/` altına JSON yazılır. Testler `EVIDRA_DATA` ile izole eder. Tamamlanmış kayıt değiştirilemez. Eksik run **404**, bozuk JSON **422**.

---

## Analysis Methodology

### 1. Şema ve yetenek

Kolonlar sabit isimle değil rolle okunur: zaman, metrik, boyut, kimlik, yok say. Yetenekler şemadan çıkar (zamansal karşılaştırma, segmentasyon, hacim–değer, ilişki, join…). Soru bu kümenin dışında kalırsa durulur.

### 2. Intent

| Intent | Örnek | Ne test edilir |
| --- | --- | --- |
| `why_change` | Satış neden değişti? | Dönem, dilim, hacim/sepet, etkileşim |
| `ranking` | Hangi kategori öne çıkıyor? | Sorulan boyut önce; güncel tutar veya en olumsuz değişim |
| `association` | Teslimat gecikmesi puanı nasıl etkiler? | İlişki testi; neden iddiası yok |

### 3. Deneyler

Kayıtlı araçlar tabloyu hesaplar. LLM, SQL veya Python üretmez. Follow-up metni asla sorgu olarak çalıştırılmaz.

### 4. Karar tipleri

| Karar | Anlamı (kullanıcı dilinde) |
| --- | --- |
| `primary_driver` | Değişim bir dilimde yoğunlaşıyor |
| `value_not_volume` | Sipariş sayısı değil, sepet tutarı |
| `ranking` | Sıralama: öne çıkan veya en olumsuz dilim |
| `data_artefact` | Güncel dönem penceresi eksik olabilir |
| `association` | İlişki var; kök neden değil |
| `abstain` | Tek kaynak işaretlenecek kadar güçlü sinyal yok |

### 5. Cevap üretimi

`analysis/response.py` donmuş run üzerinden Türkçe cümle kurar. Abstain tekrar etmez; taranan kırılımları söyler. Sorumluluk / “ilişki dilindedir” cümlesi sohbet kapanışına yazılmaz; raporun sınırlar listesinde durur.

### 6. Görselleştirme

Grafik tipi soru + kanıt işlemine göre seçilir (çizgi, sütun, şelale). Ham araç çıktısı dump edilmez. Her grafik `evidence_id` taşır. Palet: koyu mor, adaçayı, hardal, mavi, gül.

---

## Outputs

### Kullanıcıya giden

- Sohbet cevabı: tutar çifti, dilim, hacim/sepet okuması, takip chip’leri
- Rapor: yönetici özeti, KPI, grafikler, bulgular, dilim tablosu, sınırlar
- Konsol: aynı brifing + katlanabilir teknik iz
- Dashboard: son inceleme KPI + kanıt tablosu + geçmiş

### Motorda kalan

- `evidence[]` — işlem, değer, güç, dönem
- `claims[]` — yalnızca doğrulayıcıdan geçenler
- `reviews[]` — kabul / ret
- `traces[]` — araç, süre, özet
- `investigation_report` — `schema_version` v2.12

### Konsol / eval

- Golden ve product skorları
- Efficiency log (araç / deney sayısı)
- Abstain ve yasaklı dil ihlali (kapı)

---

## API

| Metod | Yol | İş |
| --- | --- | --- |
| `GET` | `/health` | Sağlık |
| `GET` | `/fixtures` | Örnek veri kataloğu |
| `POST` | `/datasets` | Fixture JSON veya multipart dosya |
| `GET` | `/datasets/{id}` | Özet ve yetenekler |
| `POST` | `/datasets/{id}/analyze` | `{ "question": "..." }` |
| `GET` | `/runs` | Run metadata listesi |
| `GET` | `/runs/{id}` | Tam run + rapor |
| `GET` | `/runs/{id}/report` | Yalnız rapor |
| `POST` | `/chats` | Sohbet aç |
| `POST` | `/chats/{id}/messages` | Tur: incele veya kanıttan cevapla |

---

## Configuration

İnceleme bütçesi (`Budget`, varsayılan): hipotez ve deney tavanı, etkileşim derinliği, `max_seconds` (60). Yükleme tavanları yukarıdaki `EVIDRA_*` değişkenleriyle değişir.

Sohbet yönlendirici (`analysis/router.py`):

- Meta: adımlar / rapor / kanıt göster
- Capability yok → abstain (motor çalışmaz)
- Dilim + “neden / ayrı incele” → scoped run
- Ranking / “bunun nedeni ne?” → donmuş kanıttan cevap
- Aksi halde yeni inceleme

---

## Technologies Used

| Katman | Teknoloji |
| --- | --- |
| Dil | Python 3.11+ |
| Tablo / SQL | pandas, DuckDB |
| İstatistik | numpy, scipy |
| Graf | LangGraph |
| API | FastAPI, uvicorn |
| Görselleştirme | Plotly |
| Sözleşme | Pydantic |
| UI | Vanilla HTML / CSS / JS |
| Test | pytest, httpx |
| Paket | uv |

**V1’e dahil değil:** çok ajanlı topoloji, RAG / vektör arama, fine-tuning, PostgreSQL, MLflow, `run_python` sandbox’ı, sahte güven skoru, raporda nedensel fiil.

---

## Business Applications

- **Değişim incelemesi:** Satış / ücret / ciro neden hareket etti, hangi dilimde toplandı.
- **Hacim vs. sepet:** Adet mi düştü, sipariş başına tutar mı.
- **Sıralama:** Hangi bölge veya kategori önde / geride.
- **Veri kalitesi:** Kesilmiş ay, eksik pencere — önce bunu söylemek.
- **İlişki (çok tablo):** Teslimat gecikmesi ve puan birlikte mi hareket ediyor (neden değil).
- **Denetlenebilir analitik:** Her iddia kanıt ID’sine iner; uydurma açıklama yok.

---

## Workflow

```text
Ham tablo
  → rol / yetenek
  → soru ∩ yetenek  (boşsa abstain)
  → kapalı hipotez sırası
  → kayıtlı deneyler + kanıt
  → yeterlilik / bütçe / dur
  → iddia doğrulama + reviewer
  → Türkçe cevap + rapor + grafik
  → sohbet follow-up (donmuş kanıt veya scoped run)
```

---

## Documentation

| Belge | Rol |
| --- | --- |
| [PLAN.md](PLAN.md) | Mimari, veri sırası, faz kapıları |
| [docs/SCHEMAS.md](docs/SCHEMAS.md) | Kilitli sözleşmeler: rol, yetenek, kanıt, araç, eval |
| [docs/DESIGN_REVIEW.md](docs/DESIGN_REVIEW.md) | Kabul / daraltma / alınmayan kararlar |
| [docs/DEMO.md](docs/DEMO.md) | 5 dakikalık tur ve ekran görüntüsü listesi |
| [docs/phases/](docs/phases/) | Faz 0–10 görev ve çıkış kriterleri |

**Veri ilerlemesi:** planted-truth sentetik fixture → Superstore → Olist (çok tablo) → UCI satır kalemi adaptörü → taksi seferi şeması. Olist V1 doğruluk seti değildir.

V1 çekirdek, **Faz 6** (eval, abstain, bütçe) UI olmadan yeşil olduğunda tamamdır. Faz 7 ince konsoldur. İsteğe bağlı Python sandbox Faz 8’dir ve atlanabilir.

---

## Screenshots

PNG’leri `docs/screenshots/` altına koy; satırlar otomatik dolar.

| Dosya | Sahne |
| --- | --- |
| `01-chat-question.png` | Soru + Türkçe cevap |
| `02-chat-preview.png` | Sağ panel KPI + grafik |
| `03-report.png` | Rapor: özet, grafik, sınırlar |
| `04-dashboard.png` | Genel bakış |
| `05-abstain.png` | Capability / sinyal yok |

Çekimden önce aynı sahneyi üret: `?fixture=clear_driver`.
