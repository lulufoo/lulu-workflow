# Tech Arch (Topic) — Architecture Quality Evaluation Framework

**Role:** EvalSoT **A** for `eval-probe-runner` dimension `arch-quality`.

Loaded via `tat_arch_quality_framework_url`. Defines P1–P4 intent gap probes and arch-only supplements.

| Layer | Artifact | Content |
|-------|----------|---------|
| **B** EvalTarget | `revision{R}/arch-doc.md` | Work artifact under review |
| **A** (this doc) | `tat_arch_quality_framework_url` | P1–P4 + arch supplements |
| **R** Section registry | `$FETCH_COMPOSE section-registry --profile lulu-arch` | `section_order`, headings, upstream graph |

Eval execution procedure (traverse **B**, load **R**, record issues) is **builtin** in `eval-probe-runner` for `arch-quality`.

**Consumer:** topic architecture shaping stage — Expand/Articulate for human sign-off before a feature cycle opens; not lulu-design solution design or lulu-plan execution specs.

---

## P1 — Semantic Fidelity

**Applies when:** Every section in **R** `section_order`.

**Checks:** Can the intent of this sub-section be accurately restated without ambiguity?

**Pass:** Restatement matches the original — no key constraint dropped, added, or shifted.

**Gap output:** `P1 — semantic drift: {description}`

---

## P2 — Negative Coverage

**Applies when:** Section has stated boundary, exclusion, or alternative to test.

**Checks:** Can at least one concrete violation of this sub-section's intent be enumerated?

**Gap output:** `P2 — boundary unclear: {description}`

---

## P3 — Logical Derivability

**Applies when:** Section key `K` has non-empty `sections.K.upstream` in **R**.

**Checks:** Can this sub-section's conclusion be derived from upstream sections without reading this sub-section?

**Gap output:** `P3 — logic chain broken: {description}`

---

## P4 — Boundary Completeness

**Applies when:** Always on the last key in **R** `section_order`; on other sections when boundary language is present.

**Checks:** Can a tricky boundary case be answered using only this sub-section's content?

**Gap output:** `P4 — boundary unanswerable: {case; what is missing}`

---

## Arch-only supplements (always apply on **B**)

### A1 — Downstream register violation

**Fail when any of:** file-level change lists; checkbox task steps; `Run:` command lines; SK/T/VF identifiers; metric threshold tables; interface field specs; acceptance criteria matrices; feature before/after outcome tables; `blocks-plan` labels (feature-cycle disposition belongs in lulu-design OQ, not arch-doc).

**Gap output:** `A1 — downstream register in arch-doc: {excerpt}`

### A2 — Open-question disposition

**Applies when:** Section key `OQ` or open-assumption language appears in **B**.

**Checks:** Each item states **blocks-next-cycle** or **non-blocking**.

**Gap output:** `A2 — OQ missing disposition: {item}`

### A3 — Structure inheritability for lulu-design

**Applies when:** Section keys `SH` or `KD`.

**Checks:** A lulu-design reader can inherit topic module partitions and architecture decision premises without chat-only context — without requiring field-level contracts or feature solution detail already present in arch-doc.

**Gap output:** `A3 — topic structure not inheritable: {what lulu-design would guess}`

### A4 — Presentation register

**Fail when:** section bodies lead with file:line chains or repository inventories instead of architecture narrative; SI lacks a reviewable topic direction before structural or decision detail appears elsewhere; content reads as single-feature solution design rather than multi-feature topic shaping.

**Gap output:** `A4 — presentation register: {violation}`

### A5 — Scope register violation

**Fail when:** enterprise-wide platform restructuring appears without decision-doc authorization; topic doc frames a single feature's implementation plan; product user-journey or business outcome narrative substitutes for architecture substance.

**Gap output:** `A5 — scope register: {violation}`

---

## Issue recording

| Field | Guidance |
|-------|----------|
| `root_cause` | `WO-ERROR` |
| `sot_ref` | `tech-arch-topic-quality-framework.md#P{n}` or `#A{n}` |
| `location` | Registry `section_key` + sub-section anchor |
| `evidence` | Quote from **B** |
