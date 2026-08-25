# Evidra — Design review (second pass)

This document records decisions after the first plan. It does not replace [PLAN.md](../PLAN.md) or [SCHEMAS.md](SCHEMAS.md). Where they disagree, this review and SCHEMAS win, and PLAN must be updated to match (this pass does that).

---

## Accepted

| Decision | Rationale |
| --- | --- |
| Single Analysis Agent through V1 | Differentiation is hypothesis → experiment → evidence → conclusion, not agent count. |
| Closed hypothesis space | Templates from column roles; policy only ranks, binds, or skips. New operators are a schema change, not a generation step. |
| Provenance on every factual claim | `evidence_id` required even when the payload is non-numeric (quality, abstention). No evidence → no claim. |
| Evidence is an engine return type | UI and report consume evidence; they do not create it. |
| Dataset order: synthetic → Superstore → Olist | Correctness, then single-table generalization, then structural multi-table benchmark. |
| Heuristic and LLM share the same graph | LLM is investigation policy, not a second product. No hard-coded Superstore narrative. |
| No `run_python` in V1 | Capability tools and `run_sql` are the computation path. |
| AST ≠ sandbox | A syntax filter on the host is not an isolated runtime. Optional Python is a later, containerized phase. |
| Capability detection | Schema-derived flags; question intersection; missing capability → abstain. |
| Abstention in V1 | Required. Delivery questions on Superstore must not spawn fake delivery hypotheses. |
| Research budget + stop | `max_hypotheses`, `max_experiments`, `max_interaction_depth`, `max_seconds`; explicit `stop_reason`. |
| No fabricated confidence | Strength is `weak \| moderate \| strong \| inconclusive`. |
| Association ≠ causation | Causal verbs rejected by the validator. `causal_analysis` is always false in V1. |
| Olist as benchmark, not V1 dataset | Join and derived delay are Phase 9. |
| CLI / API + eval before rich UI | V1 core is green at Phase 6 without UI. |

---

## Narrowed for V1

| Topic | First-pass idea | V1 slice |
| --- | --- | --- |
| Synthetic fixtures | One planted region × product break | Four fixtures: `clear_driver`, `aov_trap`, `no_signal`, `missingness`. |
| Adversarial traps | Broad “gotcha” catalogue | AOV trap + missingness in V1. Simpson / outlier / correlation-as-cause → backlog. |
| Eval size | Unbounded golden list | ~20-item **matrix** (see SCHEMAS). Not a 20×5 cartesian product. |
| Efficiency | Implicit “how many tools” | Logged (`efficiency_log`); **not** a V1 gate. |
| UI | Five equal panels including a viz pane | Core without UI; then **four blocks**: upload, question, plan, findings (charts nested) + evidence. Fifth viz panel later. |
| Python execution | Sandbox in the V1 security story | **Omitted** from V1. Phase 8 optional; skipping is valid. |
| Tool surface | `run_python` listed among V1 tools | Removed from V1 tool list. |
| Confidence | Numeric “trust” in findings | Strength enum only. |
| Causal wording | Soft “do not claim cause if weak” | Hard reject of causal verbs regardless of strength. |

---

## Not adopted (until a later explicit decision)

| Idea | Why not now |
| --- | --- |
| Multi-agent (Planner / Analyst / Statistician / Viz / Reviewer) | Topology is not the differentiator. Reviewer-as-agent is V2 and optional; V1 lock stays rule-based. |
| Opening multi-agent “for an impressive diagram” | Rejected in Phase 10: V2 is not opened to draw boxes. |
| RAG / vector DB / fine-tune / autonomous retraining | Evidra is an investigation engine over tables, not a knowledge-base chatbot. |
| PostgreSQL, MLflow, LangSmith as V1 dependencies | Observability is structured tool logs. Vendor infra is a V2 menu, one item at a time. |
| Host `RestrictedPython` as the Python story | Insufficient isolation (network, filesystem, resources). |
| Treating Olist as the correctness golden set | No single true primary driver. Process rubric only, after V1 core is green. |
| UCI Retail **and** NYC Taxi in the same V2 slice | XOR: one extra adapter. |
| Efficiency as a release gate | Log only until V2. |

---

## V1 slice (checklist)

- Four synthetic fixtures: `clear_driver`, `aov_trap`, `no_signal` (abstain), `missingness`.
- Superstore for single-table generalization and ranking / numeric items.
- ~20 eval matrix items; gates = correctness, evidence, completeness, forbidden language.
- Efficiency metrics in a log, not a gate.
- Four-block UI after core green; charts nested under findings.
- `run_python` omitted; optional isolated container later.

---

## Principle

Evidra investigates by selecting experiments from a **closed, schema-derived space**, executing them in a **deterministic engine**, and publishing only **validated, evidence-backed association claims**. Scale of orchestration, optional Python, and multi-table retail data are subsequent stress tests of that contract—not substitutes for it.
