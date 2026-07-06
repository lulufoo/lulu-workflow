# Product Blueprint (Topic) — Blueprint Quality Evaluation Framework

**Role:** EvalSoT **A** for `eval-probe-runner` dimension `blueprint-quality`.

Loaded via `pbt_blueprint_quality_framework_url`. Defines P1–P4 intent gap probes and blueprint-only supplements.

| Layer | Artifact | Content |
|-------|----------|---------|
| **B** EvalTarget | `revision{R}/product-doc.md` | Work artifact under review |
| **A** (this doc) | `pbt_blueprint_quality_framework_url` | P1–P4 + blueprint supplements |
| **R** Section registry | `$FETCH_COMPOSE section-registry --profile lulu-blueprint` | `section_order`, headings, upstream graph |

Eval execution procedure (traverse **B**, load **R**, record issues) is **builtin** in `eval-probe-runner` for `blueprint-quality`.

**Consumer:** topic product architecture shaping stage — Expand/Articulate for human sign-off before a feature cycle opens; not lulu-spec PRD or lulu-arch technical architecture.

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

## Blueprint-only supplements (always apply on **B**)

### A1 — Downstream register violation

**Fail when any of:** user-story backlogs; feature acceptance criteria matrices; technical module or API specs; interface field tables; `Run:` command lines; implementation task lists; technical architecture trade-off tables (belongs in lulu-arch).

**Gap output:** `A1 — downstream register in product-doc: {excerpt}`

### A2 — Open-question disposition

**Applies when:** Section key `OQ` or open-assumption language appears in **B**.

**Checks:** Each item states **blocks-next-cycle** or **non-blocking**.

**Gap output:** `A2 — OQ missing disposition: {item}`

### A3 — Product inheritability for lulu-approach

**Applies when:** Section keys `PS` or `PR`.

**Checks:** A lulu-approach reader can inherit topic capability partitions and product decision premises without chat-only context — without requiring technical architecture or feature PRD detail already present in product-doc.

**Gap output:** `A3 — topic product shape not inheritable: {what lulu-approach would guess}`

### A4 — Presentation register

**Fail when:** section bodies lead with implementation inventories instead of product narrative; SI lacks a reviewable topic direction before structural or decision detail appears elsewhere; content reads as single-feature PRD rather than multi-feature topic shaping.

**Gap output:** `A4 — presentation register: {violation}`

### A5 — Scope register violation

**Fail when:** enterprise-wide portfolio restructuring appears without decision-doc authorization; topic doc frames a single feature's PRD; technical architecture narrative substitutes for product substance.

**Gap output:** `A5 — scope register: {violation}`

---

## Issue recording

| Field | Guidance |
|-------|----------|
| `root_cause` | `WO-ERROR` |
| `sot_ref` | `product-blueprint-topic-quality-framework.md#P{n}` or `#A{n}` |
| `location` | Registry `section_key` + sub-section anchor |
| `evidence` | Quote from **B** |
