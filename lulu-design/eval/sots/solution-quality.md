# Design Solution Quality SoT

**Role:** EvalSoT (A) for `lulu-design` dimension `solution-quality`.
**Status:** ⚠️ Proposed runtime template.

## Boundary

This SoT defines the quality criteria for a Design EvalTarget **B**. The
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

**Gap output:** `P1 — semantic drift: {description of what shifted}`

## P2 — Negative Coverage

**Applies when:** Every unit; skip only when it has no stated boundary,
exclusion, or alternative to test.

**Checks:** Can at least one concrete violation of the unit's intent be
enumerated?

**Pass:** At least one implementation approach that would violate this intent
can be clearly named.

**Gap criteria:** No concrete violation can be enumerated — the boundary is too
vague to distinguish compliant from non-compliant behavior.

**Gap output:** `P2 — boundary unclear: {what makes violations hard to enumerate}`

## P3 — Logical Derivability

**Applies when:** The current chapter has at least one prior chapter.

**Checks:** Can the unit's conclusion be independently derived from all prior
chapters, without reading the current unit?

**Pass:** The derivation path exists and leads to the same conclusion.

**Gap criteria:** The derivation diverges from the unit's conclusion, or no
derivation path exists.

**Gap output:** `P3 — logic chain broken: {where the derivation diverges}`

## P4 — Boundary Completeness

**Applies when:** Always on the last chapter; on other chapters when boundary,
metric, or failure-mode language is present.

**Checks:** Can a tricky boundary case be answered using only the unit's
content?

**Pass:** At least one boundary case has a clear, unambiguous answer.

**Gap criteria:** The answer is ambiguous, missing, or requires information
not present in the unit.

**Gap output:** `P4 — boundary unanswerable: {case description and what is missing}`

## Design Supplements

Run after applicable P1–P4 probes. A supplement failure is `WO-ERROR`.

### D1 — Plan Register Violation

**Checks:** Body uses tech-plan or work-order register instead of design
register.

**Fail when any of:** task decomposition with checkbox steps; file-level change
lists; `Run:` command lines; SK/T/VF identifiers; phase Done markers; metric
threshold tables; runbook steps; Owner/Timing project-management tables.

**Gap output:** `D1 — plan register in design-doc: {excerpt and register type}`

### D2 — Unresolved-Item Disposition

**Applies when:** Open-assumption or unfinished process language appears in B.

**Checks:** Design-affecting assumptions are closed in `DECISION`/facts or scope
is shrunk; design-external unfinished work is on the stage agenda as a
`blocker` or `note` with clear delivery effect — not left as an Intent-section
dump.

**Gap output:** `D2 — unresolved item missing disposition: {item; needs DECISION/facts close, scope shrink, or stage-agenda blocker}`

### D3 — Design Inferability for Tech Plan

**Applies when:** The unit specifies structure or cross-boundary interfaces.

**Checks:** A tech-plan reader can instantiate structure and cross-boundary
contracts without re-deriving module partitioning, interface semantics, or
verification/operability strategy from chat-only context.

**Gap output:** `D3 — design intent not inferable: {what tech-plan would have to guess}`

### D4 — Presentation Register

**Checks:** Document-level and unit presentation complies with the applicable
domain expression conventions and section-form presentation contracts,
observable in B only.

**Fail when any of:**

- The first chapter opening lacks a reviewable engineering narrative from
  problem to approach.
- Units lead with file:line or DOM-id chains instead of engineering narrative.
- Units contain inline audit badges or evidence chains that belong in an
  appendix.
- A design changes interaction or component state but lacks explicit named
  states, transition triggers, and path end-states in a structured view.

**Gap output:** `D4 — presentation register: {observable violation}`

## Finding Record

Set `root_cause` to `WO-ERROR`; cite
`lulu-workflow/lulu-design/eval/sots/solution-quality.md#P{n}` or `#D{n}`
as `sot_ref`; quote B as evidence.
