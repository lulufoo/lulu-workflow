# Blueprint Quality SoT

**Role:** EvalSoT (A) for `lulu-blueprint` dimension `blueprint-quality`.
**Status:** ⚠️ Proposed runtime template.

## Boundary

This SoT defines the quality criteria for a Blueprint EvalTarget **B**. The
paired local Method defines traversal, prior-chapter P3 input, severity, and
finding serialization.

## P1 — Semantic Fidelity

**Applies when:** Every unit within every chapter.

**Checks:** Can the intent of the unit be accurately restated without
ambiguity?

**Pass:** A restatement matches the original — no key constraint is dropped,
added, or shifted in meaning.

**Gap criteria:** The restatement drifts, omits a constraint, introduces a new
assumption, or requires guessing the author's intent.

**Gap output:** `P1 — semantic drift: {description}`

## P2 — Negative Coverage

**Applies when:** A unit has a stated boundary, exclusion, or alternative to
test.

**Checks:** Can at least one concrete violation of the unit's intent be
enumerated?

**Pass:** At least one violating approach can be clearly named.

**Gap output:** `P2 — boundary unclear: {description}`

## P3 — Logical Derivability

**Applies when:** The current chapter has at least one prior chapter.

**Checks:** Can the unit's conclusion be derived from all prior chapters
without reading the current unit?

**Pass:** The derivation path exists and leads to the same conclusion.

**Gap output:** `P3 — logic chain broken: {description}`

## P4 — Boundary Completeness

**Applies when:** Always on the last chapter; on other chapters when boundary
language is present.

**Checks:** Can a tricky boundary case be answered using only the unit's
content?

**Pass:** At least one boundary case has a clear, unambiguous answer.

**Gap output:** `P4 — boundary unanswerable: {case; what is missing}`

## Blueprint Supplements

Run after applicable P1–P4 probes. A supplement failure is `WO-ERROR`.

### A1 — Downstream Register Violation

**Fail when any of:** user-story backlogs; feature acceptance-criteria matrices;
technical module or API specifications; interface-field tables; `Run:` command
lines; implementation task lists; technical-architecture trade-off tables.

**Gap output:** `A1 — downstream register in product-doc: {excerpt}`

### A2 — Open-Question Disposition

**Applies when:** Open-assumption language appears in B.

**Checks:** Each item states `blocks-next-cycle` or `non-blocking`.

**Gap output:** `A2 — OQ missing disposition: {item}`

### A3 — Product Inheritability for Lulu Approach

**Applies when:** A unit defines a topic capability partition or product
decision premise.

**Checks:** A `lulu-approach` reader can inherit topic capability partitions and
product decision premises without chat-only context, without requiring
technical-architecture or feature-PRD detail.

**Gap output:** `A3 — topic product shape not inheritable: {what lulu-approach would guess}`

### A4 — Presentation Register

**Fail when:** Units lead with implementation inventories rather than product
narrative; the opening lacks a reviewable topic direction before structural or
decision detail; or content reads as a single-feature PRD rather than
multi-feature topic shaping.

**Gap output:** `A4 — presentation register: {violation}`

### A5 — Scope Register Violation

**Fail when:** Enterprise-wide portfolio restructuring appears without
decision-document authorization; the topic document frames a single-feature
PRD; or technical-architecture narrative substitutes for product substance.

**Gap output:** `A5 — scope register: {violation}`

## Finding Record

Set `root_cause` to `WO-ERROR`; cite
`lulu-dev-workflow/lulu-blueprint/eval/sots/blueprint-quality.md#P{n}` or
`#A{n}` as `sot_ref`; quote B as evidence.
