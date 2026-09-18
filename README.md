# Evidra

**Evidence-bound autonomous data investigation engine**

Repository: `evidra-autonomous-data-analyst`

Evidra is not a chatbot that turns a CSV or Excel table into a fluent story. A business question is treated as a research problem: column roles are inferred, capabilities are intersected with the question, closed hypothesis templates are tested, every number is bound to an evidence object, and any sentence that cannot be bound is not published.

<!-- Image: product logo or overview frame -->
<img width="1440" height="809" alt="Dashboard" src="https://github.com/user-attachments/assets/a71aff18-8424-43b8-8f58-f027137180a1" />


---

## Overview

When a metric moves (“why did sales drop?”), several structural explanations are possible: order count contracted, basket size shrank, a single region or category pulled the change, or the current period window is truncated. Naming one of those without a registered experiment is storytelling, not investigation.

Evidra makes that path observable and auditable:

```text
QUESTION → CAPABILITIES → HYPOTHESES → EXPERIMENTS
        → EVIDENCE → DECISION → budget / stop
        → CLAIM VALIDATOR → PUBLISHED ANSWER
```

The language model (or a deterministic policy) decides **what to look at**. Python, SQL, and statistics compute. Evidence is the engine’s return type. The model is not the source of truth.

V1 report language is **association**, not causation. Strength is `weak | moderate | strong | inconclusive`. A fabricated “89% confidence” is never emitted.
<img width="1440" height="809" alt="Ekran Resmi 2026-09-18 22 35 50" src="https://github.com/user-attachments/assets/8f47068a-851a-41b1-a188-af54f5e31c85" />

---

## Key Features

- **Closed experiment space:** The engine does not invent operators. Templates are fixed: period comparison, segmentation, volume–value decomposition, interaction, anomaly, association test.
- **Capability ∩ question:** If required columns are missing (delivery delay, churn, and so on), no hypothesis is invented; the run abstains.
- **Evidence object:** Every operation is recorded with `operation`, columns, filters, period, value, and strength. Every number in the answer comes from that record.
- **Claim validator + reviewer:** Causal verbs, unbound numbers, and engine jargon are not published.
- **Research budget:** Hypothesis count, experiment count, interaction depth, and wall time stop the loop. It does not run until a narrative appears.
- **Question-aware answers:** “Why did it change?” and “which category stands out?” do not collapse into the same abstain sentence. Ranking questions test the requested slice first.
- **Multi-surface product:** Overview, analysis chat, investigation console, and detailed report all read the same investigation graph.
- **Follow-ups:** “How does West look?” is answered from frozen evidence. “Investigate West on its own” starts a scoped run in the same chat.
- **Evaluation gates:** Synthetic golden set, adversarial tables, product questions, and an efficiency overlay. Correctness and forbidden language are release gates; latency is not.

---

## Project Structure

```text
evidra-autonomous-data-analyst/
├── analysis/                     # Investigation engine and API
│   ├── api.py                    # FastAPI: datasets, chats, runs, pages
│   ├── graph.py                  # LangGraph: inspect → rank → experiment → report
│   ├── heuristic.py              # Closed-template ranking and experiment loop
│   ├── policy.py                 # Intent (why_change / ranking / association)
│   ├── router.py                 # Chat turn: investigate / answer from evidence / abstain
│   ├── response.py               # Analyst answer from frozen run state
│   ├── report.py                 # Analyst briefing + KPIs + slice table
│   ├── charts.py                 # Plotly selection from question + evidence
│   ├── chat.py                   # Chat layer (never executes SQL/Python)
│   ├── scope.py                  # Follow-up slice filter
│   ├── evidence/                 # Evidence model, scorer, validator
│   ├── tools/                    # Registered tools (DuckDB, runtime)
│   └── eval/                     # Golden, adversarial, product, efficiency
├── ui/                           # Product surfaces (vanilla HTML/CSS/JS)
│   ├── dashboard.html            # Overview
│   ├── chat.html                 # Analysis chat
│   ├── index.html                # Investigation console
│   └── report.html               # Detailed report
├── data/
│   ├── fixtures/                 # Synthetic and schema fixtures (committed)
│   ├── raw/                      # Superstore / Olist / UCI (local, not committed)
│   └── processed/runs/           # Completed investigation records
├── evals/                        # Golden, adversarial, product, rubric JSON
├── tests/                        # pytest
├── docs/                         # Architecture, schemas, phases, demo
│   └── screenshots/              # Portfolio frames (drop PNGs here)
├── PLAN.md
├── pyproject.toml
└── README.md
```

---

## Installation & Setup

### 1. Prerequisites

- Python **3.11+**
- [uv](https://docs.astral.sh/uv/) (lockfile: `uv.lock`)

### 2. Dependencies

```bash
uv sync --extra dev
```

Core packages: pandas, numpy, scipy, plotly, openpyxl, pydantic, duckdb, langgraph, fastapi, uvicorn. Dev: pytest, httpx.

### 3. Run

```bash
uv run python -m analysis.api
```

Local by default: **127.0.0.1:8765**, no login. This is still a single-operator investigation engine, not a multi-tenant SaaS.

- Overview: `http://127.0.0.1:8765/dashboard`
- Analysis chat: `http://127.0.0.1:8765/chat`
- Investigation console: `http://127.0.0.1:8765/console`
- Detailed report: `http://127.0.0.1:8765/report?run={id}`

Quick scene: `http://127.0.0.1:8765/chat?fixture=clear_driver`

To share the process on a network or a VPS, set a shared access token (and bind beyond loopback only when that token is set):

```bash
EVIDRA_HOST=0.0.0.0 EVIDRA_ACCESS_TOKEN=choose-a-long-secret uv run python -m analysis.api
```

The UI then asks for the token once and stores it in an HTTP-only cookie. `GET /health` stays open. There is no user table, OAuth, or per-tenant isolation.

Optional: `EVIDRA_PORT` (default `8765`).

---

## Usage Guide

### Product surfaces

**Overview (`/dashboard`)**  
Latest-run KPIs, evidence-bound charts, a sortable slice table, past reports, and a system summary. This is an analyst home screen, not a landing page.

<img width="1440" height="809" alt="Main Dashboard" src="https://github.com/user-attachments/assets/10601dab-f2d5-4ec1-9fb5-84805f3091ed" />


**Analysis chat (`/chat`)**  
Bind a dataset (sample fixture or CSV/Excel) and ask a business question. The answer is analyst prose: previous → current amount, concentrated slice, volume/basket reading. The right panel shows the workflow, KPIs, and a chart; each message has a time and status line.

<img width="1440" height="809" alt="Chat Review" src="https://github.com/user-attachments/assets/7c305ad2-7cd5-43ab-87bc-deff9c0a93f7" />

<img width="1440" height="809" alt="Chat Board" src="https://github.com/user-attachments/assets/ee0afdcf-e852-4a91-84e6-e3a47d075012" />


**Investigation console (`/console`)**  
Four steps: dataset → business question → how it was examined → result (KPIs, charts, slice table). Tool traces, evidence IDs, and review records sit in a foldable technical section.

**Detailed report (`/report`)**  
The same summary as chat, plus a KPI strip, charts, headline findings, next questions, a slice table, and “what this report does not claim.” Engine jargon stays in the appendix.

<img width="1440" height="809" alt="Report" src="https://github.com/user-attachments/assets/9937e6f2-93b2-4964-970f-7111b18600e4" />

<img width="1440" height="809" alt="KPI Screen" src="https://github.com/user-attachments/assets/2838cb9c-9638-462b-ad06-cf8067860541" />



### Example questions

| Data | Question | Expected behavior |
| --- | --- | --- |
| Clear concentration (`clear_driver`) | Satış neden değişti? | West × Office Supplies; amount and share |
| Follow-up on the same run | Hangi kategori öne çıkıyor? | Ranking on the category slice |
| Follow-up on the same run | West bölgesindeki Office Supplies neden düştü? | Scoped run, new investigation |
| AOV trap (`aov_trap`) | Satış neden değişti? | Basket size, not order count |
| No signal (`no_signal`) | Satış neden değişti? | Abstain; no single source named |
| Taxi (`taxi_trips`) | Ücret neden değişti? | Fare language, not “sales” |
| Superstore (local) | Hangi bölge öne çıkıyor? | Ranking; Region first |
| Delivery / churn | Teslimat gecikmesi puanı nasıl etkiler? | Abstain if the capability is missing |


The product UI is Turkish; the questions above are the ones the surfaces actually ask.

### CLI investigation

Same graph, no API:

```bash
uv run python -m analysis.graph \
  --data data/fixtures/clear_driver.csv \
  --question "Satış neden değişti?"
```

Olist (multi-table; local files under `data/raw/`):

```bash
uv run python -m analysis.graph \
  --data data/raw \
  --question "Teslimat gecikmesi ile review score arasında association var mı?"
```

### Evaluation

```bash
uv run python -m analysis.eval
uv run pytest
```

Sub-suites:

```bash
uv run python -m analysis.eval.efficiency
uv run python -m analysis.eval.adaptive
```

Golden matrix: `evals/golden.json` (~20 items: driver, trap, abstain, interaction, temporal, anomaly, numerical, budget). Gates: numerical correctness, evidence binding, `stop_reason` completeness, forbidden language. Tool counts and latency go to `evals/out/efficiency_log.jsonl` and are **not** a release gate.

---

## Data & Fixtures

| Fixture | File | Purpose |
| --- | --- | --- |
| `clear_driver` | `data/fixtures/clear_driver.csv` | Clear concentration in one slice |
| `aov_trap` | `data/fixtures/aov_trap.csv` | Volume flat, basket down |
| `no_signal` | `data/fixtures/no_signal.csv` | Diffuse change; abstain |
| `missingness` | `data/fixtures/missingness.csv` | Missing / truncated window |
| `taxi_trips` | `data/fixtures/taxi_trips.csv` | Geo + time; fare metric |
| `superstore` | `data/raw/superstore.csv` | Single-table generalization (local) |
| `olist` | `data/raw/` | Multi-table (local, not committed) |
| `uci_retail` | `data/fixtures/retail_line_items.csv` | Line-item schema adapter |

Uploads (HTTP multipart only — not fixture/CLI): default 10 MiB, 50,000 rows, 64 columns. Oversize is **413**, shape/filename errors are **400**. Env: `EVIDRA_MAX_UPLOAD_BYTES`, `EVIDRA_MAX_UPLOAD_ROWS`, `EVIDRA_MAX_UPLOAD_COLUMNS`, `EVIDRA_MAX_UPLOAD_CELL_LENGTH`.

Completed runs are written as JSON under `data/processed/runs/`. Tests isolate persistence with `EVIDRA_DATA`. Completed records are immutable. Missing run is **404**, corrupt JSON is **422**.

---

## Analysis Methodology

### 1. Schema and capabilities

Columns are read by role, not by hardcoded name: time, metric, dimension, identifier, ignore. Capabilities come from that schema (temporal comparison, segmentation, volume–value, association, join…). If the question sits outside that set, the run stops.

### 2. Intent

| Intent | Example | What is tested |
| --- | --- | --- |
| `why_change` | Satış neden değişti? | Period, slice, volume/basket, interaction |
| `ranking` | Hangi kategori öne çıkıyor? | Requested dimension first; current amount or worst change |
| `association` | Teslimat gecikmesi puanı nasıl etkiler? | Association test; no causal claim |

### 3. Experiments

Registered tools compute on the table. The LLM does not emit SQL or Python. Follow-up text is never executed as a query.

### 4. Decision types

| Decision | Meaning |
| --- | --- |
| `primary_driver` | The change concentrates in one slice |
| `value_not_volume` | Basket size, not order count |
| `ranking` | Ranking: leading or worst slice |
| `data_artefact` | Current period window may be incomplete |
| `association` | Association exists; not a root cause |
| `abstain` | No signal strong enough to name one source |

### 5. Answer composition

`analysis/response.py` writes the analyst sentence from frozen run state. Abstain does not repeat itself; it names the dimensions that were scanned. The boilerplate “this is association language” sentence is not appended to chat; it lives in the report limitations list.

### 6. Visualization

Chart type is chosen from the question plus the evidence operation (line, bar, waterfall). Raw tool payloads are not dumped. Every chart cites `evidence_id`. Palette: deep purple, sage, mustard, blue, rose.

---

## Outputs

### User-facing

- Chat answer: amount pair, slice, volume/basket reading, follow-up chips
- Report: executive summary, KPIs, charts, findings, slice table, limitations
- Console: the same briefing plus a foldable technical trace
- Dashboard: latest-run KPIs + evidence table + history

### Engine-internal

- `evidence[]` — operation, value, strength, period
- `claims[]` — only those that pass the validator
- `reviews[]` — accept / reject
- `traces[]` — tool, duration, summary
- `investigation_report` — `schema_version` v2.12

### Eval / console

- Golden and product scores
- Efficiency log (tool / experiment counts)
- Abstain and forbidden-language violations (gate)

---

## API

| Method | Path | Role |
| --- | --- | --- |
| `GET` | `/health` | Health |
| `GET` | `/fixtures` | Sample dataset catalog |
| `POST` | `/datasets` | Fixture JSON or multipart file |
| `GET` | `/datasets/{id}` | Overview and capabilities |
| `POST` | `/datasets/{id}/analyze` | `{ "question": "..." }` |
| `GET` | `/runs` | Run metadata list |
| `GET` | `/runs/{id}` | Full run + report |
| `GET` | `/runs/{id}/report` | Report only |
| `POST` | `/chats` | Open a chat |
| `POST` | `/chats/{id}/messages` | Turn: investigate or answer from evidence |

---

## Configuration

Investigation budget (`Budget`, defaults): hypothesis and experiment caps, interaction depth, `max_seconds` (60). Upload caps are the `EVIDRA_*` variables above.

Chat router (`analysis/router.py`):

- Meta: show steps / report / evidence
- Missing capability → abstain (engine does not run)
- Slice + “why / investigate separately” → scoped run
- Ranking / “what is the cause?” → answer from frozen evidence
- Otherwise a new investigation

---

## Technologies Used

| Layer | Technology |
| --- | --- |
| Language | Python 3.11+ |
| Tables / SQL | pandas, DuckDB |
| Statistics | numpy, scipy |
| Graph | LangGraph |
| API | FastAPI, uvicorn |
| Visualization | Plotly |
| Contracts | Pydantic |
| UI | Vanilla HTML / CSS / JS |
| Tests | pytest, httpx |
| Packaging | uv |

**Not in V1:** multi-agent topology, RAG / vector search, fine-tuning, PostgreSQL, MLflow, a `run_python` sandbox, fake confidence scores, causal verbs in reports.

---

## Business Applications

- **Change investigation:** Why sales / fare / revenue moved, and which slice absorbed it.
- **Volume vs. basket:** Order count vs. amount per order.
- **Ranking:** Which region or category leads or lags.
- **Data quality:** Truncated month or missing window — say that first.
- **Association (multi-table):** Whether delivery delay and review score move together (not why).
- **Auditable analytics:** Every claim traces to an evidence ID; no invented explanation.

---

## Workflow

```text
Raw table
  → roles / capabilities
  → question ∩ capability  (empty → abstain)
  → closed hypothesis rank
  → registered experiments + evidence
  → sufficiency / budget / stop
  → claim validation + reviewer
  → analyst answer + report + charts
  → chat follow-up (frozen evidence or scoped run)
```

---

## Documentation

| Document | Role |
| --- | --- |
| [PLAN.md](PLAN.md) | Architecture, dataset sequence, phase gates |
| [docs/SCHEMAS.md](docs/SCHEMAS.md) | Locked contracts: roles, capabilities, evidence, tools, eval |
| [docs/DESIGN_REVIEW.md](docs/DESIGN_REVIEW.md) | Accepted, narrowed, and rejected decisions |
| [docs/DEMO.md](docs/DEMO.md) | Five-minute tour and screenshot list |
| [docs/phases/](docs/phases/) | Phases 0–10: tasks and exit criteria |

**Data progression:** planted-truth synthetic fixtures → Superstore → Olist (multi-table) → UCI line-item adapter → taxi-trip schema. Olist is not the V1 correctness set.

The V1 core is complete when **Phase 6** (eval, abstention, budget) is green **without** UI. Phase 7 is a thin console. Optional Python sandbox is Phase 8 and may be skipped.

---

## Screenshots

Drop PNGs under `docs/screenshots/`; uncomment the image lines above.

| File | Scene |
| --- | --- |
| `01-chat-question.png` | Question + analyst answer |
| `02-chat-preview.png` | Side panel KPIs + chart |
| `03-report.png` | Report: summary, charts, limitations |
| `04-dashboard.png` | Overview |
| `05-abstain.png` | Missing capability / no signal |

Produce the same scene first: `?fixture=clear_driver`.
