# Evidra — Locked schemas (V1)

Contracts below are binding for implementation. Phase documents may refine field names; they may not reopen the closed sets or weaken the validator.

Source of truth for product intent: [PLAN.md](../PLAN.md), [DESIGN_REVIEW.md](DESIGN_REVIEW.md).

---

## 1. Investigation loop

```text
QUESTION
  → CAPABILITIES          (from schema, not from the question alone)
  → INTERSECT / ABSTAIN   (empty intersection → stop, no hypotheses)
  → HYPOTHESES            (rank / bind / skip closed templates)
  → EXPERIMENTS           (registered tools only)
  → EVIDENCE              (engine return type, append-only)
  → DECISION              (score, keep / drop)
  → budget / STOP
  → CLAIM VALIDATOR
  → FINAL CLAIMS
```

The language model (when present) is **investigation policy**: it may rank templates, bind columns already in the role table, and skip templates. It may not invent a new `template_id` or a new tool name.

---

## 2. Column roles and capabilities

### ColumnRole

| Field | Values |
| --- | --- |
| `name` | Column name in the source |
| `role` | `time` \| `metric` \| `dimension` \| `id` \| `ignore` |
| `semantic` | e.g. `sales`, `profit`, `quantity`, `customer`, `region`, `product`, `discount` |
| `dtype` | Expected type |
| `nullable` | boolean |

Roles are inferred; source names (`Order Date` vs `order_date` vs `Tarih`) are not hard-coded.

### Capabilities

Detected from the role table. Not a wish list from the prompt.

| Capability | Typical requirement | V1 |
| --- | --- | --- |
| `temporal_analysis` | ≥1 `time`, ≥1 `metric` | schema |
| `segmentation` | ≥1 `dimension`, ≥1 `metric` | schema |
| `metric_comparison` | ≥1 `metric` | schema |
| `volume_value_decomposition` | volume proxy (`id` or count) + value `metric` | schema |
| `interaction` | ≥2 `dimension` + `metric` | schema |
| `anomaly_detection` | numeric `metric` (optionally `time`) | schema |
| `association` | ≥2 numeric columns, or metric × dimension | schema |
| `causal_analysis` | — | **always `false` in V1** |
| `multi_table_join` | ≥2 registered tables + join keys | Olist / Phase 9 |
| `delivery_analysis` | order / ship / delivery timestamps | Olist / Phase 9 |
| `retention_analysis` | repeat-customer identifiers over time | Olist / Phase 9 |

**Intersect:** `supported_capabilities ∩ question_required_capabilities`.

**Abstain:** if the intersection is empty, emit an abstention claim, set `stop_reason: abstain`, and **do not** generate hypotheses.

Example: a delivery-delay question on Superstore → `delivery_analysis` missing → abstain.

---

## 3. Hypothesis (closed template space)

The hypothesis space is **closed**. Policy (heuristic or LLM) may only **rank**, **bind**, or **skip**.

| Field | Meaning |
| --- | --- |
| `hypothesis_id` | Stable id in the run |
| `template_id` | Closed set below |
| `bindings` | Column / period bindings from the role table |
| `status` | `ranked` \| `bound` \| `skipped` \| `tested` \| `dropped` |
| `selected_by` | `heuristic` \| `llm` |

### Closed `template_id` set

| `template_id` | Experiment map |
| --- | --- |
| `temporal_change` | `compare_periods` |
| `volume_vs_value` | `decompose_volume_value` |
| `segment_driver` | `segment_by` (one dimension) |
| `interaction` | `segment_by` (two dimensions) |
| `association` | `statistical_test` |
| `data_artefact` | quality / missingness / duplicate / period-window checks |
| `anomaly` | `detect_anomalies` |

An allowlist miss (unknown `template_id` from the model) **fails** the run or that step; it is not coerced into a nearby template.

---

## 4. Evidence and claims

Evidence is the **engine’s return type**, not a UI decoration.

### Evidence

| Field | Meaning |
| --- | --- |
| `evidence_id` | Stable id |
| `operation` | Tool / function name |
| `source_columns` | Columns used |
| `filters` | Applied filters |
| `period` | Window (previous / current / custom) |
| `value` | Structured numeric or tabular payload |
| `strength` | `weak` \| `moderate` \| `strong` \| `inconclusive` |

`strength` is assigned by a **scorer** (rules on magnitude, share of total change, separation). The LLM does not assign strength.

### Claim

| Field | Meaning |
| --- | --- |
| `claim_id` | Stable id |
| `text` | Sentence shown to the user |
| `kind` | `association` \| `ranking` \| `quality` \| `abstention` |
| `evidence_ids` | Non-empty for factual kinds; abstention may cite capability evidence |
| `provenance_ok` | Set by the validator |

**No evidence → no claim.** A factual sentence without `evidence_ids` is dropped. Charts carry `evidence_ids`; a figure is not an independent source of numbers.

### Claim validator (V1)

1. Every factual claim has ≥1 `evidence_id` present in the run’s evidence log.
2. Numbers in `text` must match evidence payloads (tolerance defined in eval).
3. Causal verbs / nouns are **rejected**: English `cause`, `because`, `root cause`; Turkish `sebep`, `neden oldu` as causal assertion, and equivalent “X caused Y” forms. V1 language is association (“associated with”, “accounts for share of change”, “co-occurs”).
4. `kind` must not be causal. `causal_analysis` remains false.
5. Strength labels in text, if any, must equal the scorer’s enum — no “89% confidence”.

---

## 5. RunState

| Field | Meaning |
| --- | --- |
| `question` | User question |
| `dataset_id` | Loaded dataset |
| `roles` | ColumnRole[] |
| `capabilities` | Detected capability flags |
| `plan` | Ordered steps (tool, status, duration) |
| `hypotheses` | Hypothesis[] |
| `evidence` | **Append-only** Evidence[] |
| `claims` | Claim[] after validation |
| `charts` | Plotly JSON + `evidence_ids` |
| `traces` | Structured tool log |
| `budget` | See below |
| `stop_reason` | `strong_evidence` \| `space_exhausted` \| `budget` \| `abstain` |
| `report` | Validated claims only |

### Budget (V1, mandatory)

| Limit | Default |
| --- | --- |
| `max_hypotheses` | 8 |
| `max_experiments` | 20 |
| `max_interaction_depth` | 2 |
| `max_seconds` | implementation-defined, must exist |

Hitting a limit sets `stop_reason: budget` and still runs the claim validator on evidence collected so far.

---

## 6. V1 tools

Registered names only. Structured calls. No `run_python` in V1.

| Tool | Role |
| --- | --- |
| `inspect_dataset` | Shape, types, sample |
| `profile_dataset` | Quality, roles, summary |
| `detect_capabilities` | Capability flags from roles |
| `compare_periods` | Previous / current / change |
| `segment_by` | One or two dimensions |
| `decompose_volume_value` | Volume vs AOV / value |
| `test_hypothesis` | Bind template → experiment → evidence |
| `detect_anomalies` | IQR / z / temporal deviation |
| `statistical_test` | Statistic + p-value; **not** causal prose |
| `create_chart` | Plotly JSON tied to `evidence_ids` |
| `run_sql` | DuckDB `SELECT` only, row limit |
| `generate_report` | Claims that passed the validator |

There is no one-off tool such as `calculate_monthly_sales`. That is an experiment (`compare_periods` / SQL), not a new capability.

---

## 7. EvalItem and gates

Eval is a **matrix of ~20 items**, not a 20×5 cartesian product.

### EvalItem (fields)

| Field | Meaning |
| --- | --- |
| `id` | Stable item id |
| `dataset_id` | Fixture or Superstore id |
| `question` | Prompt |
| `required_capabilities` | For abstention tests |
| `expected` | Driver, ranking, numeric band, or `abstain` |
| `metric_type` | `driver` \| `trap` \| `abstain` \| `interaction` \| `temporal` \| `anomaly` \| `numerical` |
| `forbidden_language` | Must not appear |

### Target mix (~20)

| Count | Type |
| --- | --- |
| 5 | driver recovery |
| 3 | traps (e.g. AOV vs volume) |
| 3 | abstain |
| 3 | interaction |
| 2 | temporal |
| 2 | anomaly |
| 2 | numerical |

Simpson, outlier-as-driver, and correlation-as-cause traps are **backlog**, not V1 fixtures.

### Gates vs efficiency

| Class | V1 gate? |
| --- | --- |
| Correctness (numeric, driver, ranking) | Yes |
| Evidence coverage / unbound claims | Yes |
| Completeness (loop ran until a valid stop) | Yes |
| Forbidden language | Yes |
| Tool-name match | `efficiency_log` only |
| Latency / token cost | `efficiency_log` only |

---

## 8. Report language

**Allowed (V1):** association, ranking, quality, abstention; share of change; previous / current / delta; strength enum; “insufficient evidence”.

**Disallowed:** cause, because (causal), root cause, `sebep` as causation, “X caused Y”, fabricated confidence percentages, numbers not present in evidence, claims that require `causal_analysis` or missing capabilities.

---

## 9. Reviewer (V2.1)

Locked in [phases/10-reviewer.md](phases/10-reviewer.md). Not a V1 tool. Sits after claim validation, before report. Does not append evidence or call analysis tools.

`ReviewVerdict.decision`: `accept` \| `reject` \| `revise` \| `abstain`. `revise` may only narrow wording/kind; it may not invent numbers. Claim objects do not gain a numeric confidence field. Strength remains on Evidence.

---

## 10. Investigation report (V2.6)

`investigation_report` is derived **after** validation and review. It does not draft claims or execute tools. Charts are optional, purpose-selected, and must cite `evidence_ids`. Chart y-values come from evidence payloads. A fixed chart count is not part of the contract.

Sections: executive summary, dataset overview, question, plan, research trace, key findings, evidence, driver decomposition, visualizations, statistical results, reviewer decisions, limitations, recommended next investigations.

---

## 11. Retail line-item adapter (V2.7)

Invoice-style tables (UCI Online Retail II schema) are canonicalized in the adapter: missing value metric → `amount` = quantity × unit price; cancelled/negative lines dropped. Core tools are unchanged. Detection is schema tokens, not a `calculate_uci_*` tool.



