# Evidra — Autonomous Data Analysis & Investigation Engine

**Repo:** `evidra-autonomous-data-analyst`  
**Ürün adı:** Evidra  

Evidra, veriyi “analiz etmesi için” bir dile model vermez. Kapalı bir hipotez uzayından deney seçer, kayıtlı tool’larla hesaplar, engine’in ürettiği evidence nesnelerine kilitler ve yalnızca validator’dan geçen claim’leri yayımlar.

> Investigation system: policy (LLM or heuristic) decides *what* to test; the engine computes; evidence decides *what may be claimed*.

Bu dosya projenin **genel planıdır**. Sözleşmeler: [docs/SCHEMAS.md](docs/SCHEMAS.md). İkinci geçiş kararları: [docs/DESIGN_REVIEW.md](docs/DESIGN_REVIEW.md).

| Aşama | Dosya | Kapı |
| --- | --- | --- |
| 0 | [docs/phases/00-sozlesme.md](docs/phases/00-sozlesme.md) | Sistem sözleşmesi kilitlendi |
| 1 | [docs/phases/01-synthetic-capability.md](docs/phases/01-synthetic-capability.md) | Roller + capability sözlüğü + 4 fixture |
| 2 | [docs/phases/02-analysis-engine.md](docs/phases/02-analysis-engine.md) | LLM’siz computation layer |
| 3 | [docs/phases/03-evidence-provenance.md](docs/phases/03-evidence-provenance.md) | Evidence/Claim + validator |
| 4 | [docs/phases/04-tools-heuristic.md](docs/phases/04-tools-heuristic.md) | Tool I/O; aynı graf, heuristic |
| 5 | [docs/phases/05-investigation-policy.md](docs/phases/05-investigation-policy.md) | LangGraph; LLM yalnızca template seçimi |
| 6 | [docs/phases/06-eval-abstention-budget.md](docs/phases/06-eval-abstention-budget.md) | **V1 core:** eval + abstention + budget (UI yok) |
| 7 | [docs/phases/07-minimal-ui.md](docs/phases/07-minimal-ui.md) | 4 blok konsol; ajan davranışı değişmez |
| 8 | [docs/phases/08-optional-python.md](docs/phases/08-optional-python.md) | İsteğe bağlı izole Python; atlamak geçerli |
| 9 | [docs/phases/09-olist.md](docs/phases/09-olist.md) | Çok tablolu yapısal benchmark |
| 10 | [docs/phases/10-v2.md](docs/phases/10-v2.md) | V2.1–V2.4; Adaptive Research [10-v2.4-adaptive.md](docs/phases/10-v2.4-adaptive.md) |

**Kural:** Bir aşamanın çıkış kriteri yeşil olmadan sonrakine geçilmez. Takvim yok; çıkış kriteri var. V1 **core** Aşama 6’da UI’sız yeşil olur. Olist Aşama 9’dur, V1 dataset’i değildir.

---

## Döngü

```text
QUESTION → CAPABILITIES → HYPOTHESES → EXPERIMENTS
        → EVIDENCE → DECISION → budget / stop
        → CLAIM VALIDATOR → FINAL CLAIMS
```

Hipotez uzayı **kapalıdır**. Policy (heuristic veya LLM) template’leri rank / bind / skip eder; yeni operatör uydurmaz.

---

## V1 mimari (tek ajan)

Tek **Analysis Agent**. Serbest ReAct yok. Zorunlu graf (Aşama 5):

```text
inspect → profile → detect_capabilities → intersect
       → rank_hypotheses → experiment_loop → score
       → stop → validate_claims → report
```

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ Policy      │     │ Tools / engine   │     │ Evidence    │
│ heuristic   │────▶│ registered ops   │────▶│ append-only │
│ or LLM rank │     │ SQL SELECT       │     │ scorer      │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                    │
                                            ┌───────▼────────┐
                                            │ Claim validator│
                                            │ association only│
                                            └────────────────┘
```

LLM yoksa heuristic **aynı grafı** doldurur. API anahtarı ürünü durdurmaz. Superstore’a gömülü sabit rapor yoktur.

**Yetenek tool’ları (V1 — `run_python` yok)**

- `inspect_dataset`
- `profile_dataset`
- `detect_capabilities`
- `compare_periods`
- `segment_by`
- `decompose_volume_value`
- `test_hypothesis`
- `detect_anomalies`
- `statistical_test`
- `create_chart`
- `run_sql` (DuckDB, yalnızca SELECT)
- `generate_report`

**V1’de yok**

- Multi-agent (Planner / Analyst / Statistician / Viz / Reviewer)
- RAG, vector DB, fine-tune
- PostgreSQL, MLflow, LangSmith
- `run_python` (AST tek başına sandbox sayılmaz)
- Sahte yüzde güven; nedensel fiil
- Olist’i correctness golden’ı saymak
- Core kapısı olarak 5. viz paneli

State: `question`, `dataset_id`, `roles`, `capabilities`, `plan`, `hypotheses`, `evidence` (append-only), `claims`, `charts`, `traces`, `budget`, `stop_reason`, `report`.

---

## Dataset üçlüsü

Farklılaştırıcı tablo sayısı değil; **hypothesis → experiment → evidence → conclusion**.

| Sıra | Dataset | Rol |
| --- | --- | --- |
| 0 | Sentetik (4 fixture) | **Correctness** — gömülü gerçek |
| 1 | Superstore (tek tablo) | **Generalization** — isim hardcode yok |
| 2 | Olist (çok tablo) | **Structure** — join, gecikme, review; Aşama 9 |

V1 sentetik fixture’lar: `clear_driver`, `aov_trap`, `no_signal` (abstain), `missingness`. Simpson / outlier / korelasyon-tuzağı backlog.

Büyük ham CSV **repoya konmaz**. `data/` gitignore; küçük fixture commit edilir.

---

## Dil ve güven

- Strength: `weak | moderate | strong | inconclusive`. “89% confidence” yok.
- V1 dili **association**. `cause`, `because`, `sebep`, `root cause` validator’da reddedilir.
- Capability yoksa abstention; hipotez üretilmez.
- Research budget zorunlu; `stop_reason`: `strong_evidence | space_exhausted | budget | abstain`.

---

## Teknik stack (V1 core)

| Katman | Seçim |
| --- | --- |
| API / CLI | FastAPI + CLI (Aşama 6 kapısı CLI/API+eval) |
| Ajan | LangGraph state machine (Aşama 5+) |
| Veri | Pandas + DuckDB |
| Viz | Plotly JSON (UI’da nested; 5. panel sonra) |
| LLM | Opsiyonel; heuristic aynı graf |
| UI | Aşama 7: 4 blok |
| Eval | ~20 maddelik matris; efficiency log, gate değil |
| Gözlem | yapılandırılmış tool log |
| Paket | README; Dockerfile ihtiyaç olunca |

---

## Başarı tanımı

**V1 bitti = Aşama 6 yeşil:** LLM kapalıyken sentetik matris (sürücü, tuzak, abstain, evidence, yasak dil) geçer; budget durur; UI gerekmez.

Olist (Aşama 9) V1’in yerine geçmez; core yeşil olduktan sonra yapısal sınavdır.

---

## Nasıl ilerlenir?

1. Bu dosya + SCHEMAS + DESIGN_REVIEW kaynak kabul edilir.
2. Açık aşamanın görevleri sırayla bitirilir.
3. Çıkış kriteri işaretlenir; sonrakine geçilir.
4. Klasör ormanı ilk günde şişirilmez.

İlk uygulama kodu Aşama 0 kilit + Aşama 1 fixture/capability sözlüğünden sonra gelir. LangGraph, engine ve evidence şeması ayağa kalkmadan kurulmaz.
