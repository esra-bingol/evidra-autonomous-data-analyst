# Evidra

**Autonomous Data Analysis & Investigation Engine**

Repository: `evidra-autonomous-data-analyst`

Evidra is not an LLM that analyzes data. It is an investigation system that uses an LLM (or a deterministic policy) to decide what to investigate, registered tools to compute results, and an evidence layer to decide what may legitimately be claimed.

---

## Purpose

A business question over a table is treated as a **research problem** with a closed experimental space, not as a prompt that generates an analysis.

Given a spreadsheet (and, later, related tables), Evidra should:

1. Infer **column roles** (time, metric, dimension, identifier, ignore) without hard-coding source names.
2. Detect **capabilities** from that schema (temporal comparison, segmentation, volume–value decomposition, and so on).
3. **Intersect** those capabilities with the question; if the intersection is empty, **abstain** and do not invent hypotheses.
4. Rank, bind, or skip hypotheses from a **closed template set**. The model does not invent new operators.
5. Run experiments through a deterministic engine and persist **evidence objects** (operation, columns, filters, period, value, strength).
6. Emit claims only after a **claim validator**: every factual claim carries `evidence_id`s; forbidden causal language is rejected.
7. Stop under an explicit **research budget** (hypothesis, experiment, interaction depth, wall time) rather than looping until a narrative appears.

The language model is an **investigation policy** (intent, ranking of templates, wording of association claims). Python, SQL, and statistics are the **computation layer**. Evidence is the engine’s return type. The model is not the source of truth.

---

## Problem

Asking a model to “analyse this CSV” collapses investigation into one generation step. The result is often a fluent story, a generic aggregation, or a causal sentence the data never supported.

A change in a metric admits structurally different explanations (volume vs. value, a single segment, an interaction, a missingness artefact). Naming one of them without a registered experiment is not investigation.

Evidra makes the path **observable and auditable**: capabilities, ranked templates, experiments, evidence, then claims that survive validation.

---

## Claim

A complete run is defined as:

```text
QUESTION → CAPABILITIES → HYPOTHESES → EXPERIMENTS
        → EVIDENCE → DECISION → budget / stop
        → CLAIM VALIDATOR → FINAL CLAIMS
```

If a statement cannot be traced to an evidence object produced by the engine, it does not ship. Strength is `weak | moderate | strong | inconclusive`, never a fabricated percentage. V1 report language is **association**, not causation.

This is the standard used in evaluation: numerical correctness, primary-driver recovery on fixtures with planted ground truth, evidence coverage, completeness of the investigation loop, and rejection of unbound or causal claims.

---

## Scope (this repository)

Implementation follows staged work orders with exit criteria. Application code is added when the corresponding phase is open.

| Document | Role |
| --- | --- |
| [PLAN.md](PLAN.md) | Architecture, dataset sequence, phase gates |
| [docs/SCHEMAS.md](docs/SCHEMAS.md) | Locked contracts: roles, capabilities, evidence, state, tools, eval |
| [docs/DESIGN_REVIEW.md](docs/DESIGN_REVIEW.md) | Second-pass decisions: accepted, narrowed, not adopted |
| [docs/phases/](docs/phases/) | Phases 0–10: tasks and exit criteria |

**Data progression:** synthetic fixtures with planted ground truth (correctness) → Superstore (single-table generalization) → Olist (structural multi-table benchmark). Olist is not a V1 dataset.

**V1 includes:** a single Analysis Agent; closed hypothesis templates; capability detection and abstention; research budget and stop conditions; evidence as an engine return type; claim validation; heuristic and optional LLM sharing the same graph; CLI/API and eval as the core product; a later minimal four-block UI.

**V1 excludes:** multi-agent topology; RAG / vector search; fine-tuning; PostgreSQL, MLflow, vendor tracing; `run_python` (AST alone is not a sandbox); fake confidence scores; causal verbs in reports; a fifth visualization panel as a core gate; treating Olist as the V1 correctness set. Simpson / outlier / correlation-trap tables are a **V2.2 measurement set**, not V1 golden correctness.


V1 core is green when **Phase 6** (eval, abstention, budget) passes **without** requiring UI. Phase 7 is a thin console over the same core. Optional sandboxed Python is Phase 8 and may be skipped. Olist is Phase 9.

---

## Setup

Python ≥ 3.11. Install with [uv](https://docs.astral.sh/uv/) (lockfile: `uv.lock`):

```bash
uv sync --extra dev
```

---

## Evaluation (V1 core)

Heuristic policy, no UI:

```bash
uv run python -m analysis.eval
uv run pytest tests/test_eval.py tests/test_analysis_engine.py tests/test_evidence.py tests/test_heuristic.py tests/test_graph.py tests/test_api.py tests/test_reviewer.py tests/test_adversarial.py tests/test_efficiency.py tests/test_adaptive.py
```

Golden matrix: `evals/golden.json` (~20 items: driver, trap, abstain, interaction, temporal, anomaly, numerical, plus a budget item). Gates are correctness, evidence binding, completeness (`stop_reason`), and forbidden language. Tool counts and latency go to `evals/out/efficiency_log.jsonl` and are **not** a release gate.

Adversarial tables (`evals/adversarial.json`, V2.2) score robustness separately. Language and missing-capability locks still gate; remaining categories are reported, not used to rewrite the engine.

Efficiency (`python -m analysis.eval.efficiency`, V2.3) overlays tool/experiment counts on the same suites. It does not override correctness. Proposed caps come from measured golden maxima and are **not** a release gate.

Adaptive Research (`python -m analysis.eval.adaptive`, V2.4) continues with a closed template only when evidence is insufficient, and records a `reason` per follow-up. Budget exhaustion abstains. The V1 golden matrix is unchanged.

---

## Console (Phase 7)

Same investigation graph. No fifth visualization panel. Local, no auth. Port **8765** (not 3000 / 5173 / 8080).

```bash
uv sync --extra dev
uv run python -m analysis.api
```

Open `http://127.0.0.1:8765`. Four blocks: dataset, question, plan, findings + nested charts and evidence.

API:

- `POST /datasets` — JSON `{ "fixture_id": "clear_driver" }` or `{ "fixture_id": "olist" }`, or multipart CSV/Excel/zip
- `GET /datasets/{id}` — overview / capabilities
- `POST /datasets/{id}/analyze` — `{ "question": "..." }`
- `GET /runs/{id}` — plan, claims, evidence, charts, traces, `stop_reason`

Olist (Phase 9, local CSVs in `data/raw/`, not committed). Demo:

```bash
uv run python -m analysis.graph --data data/raw --question "Teslimat gecikmesi ile review score arasında association var mı?"
```

Rubric (not a city golden): `evals/olist_rubric.json`. V1 matrix must still pass.

