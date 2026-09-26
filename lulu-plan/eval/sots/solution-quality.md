# Plan Solution Quality SoT

**Role:** Primary EvalSoT (A) for `lulu-plan` dimension `solution-quality`.
**Status:** ⚠️ Proposed runtime template.

## P1 — Semantic Fidelity

**Applies when:** Always.

**Checks:** Can the intent of this unit be accurately restated without
ambiguity?

**Pass:** The restatement preserves every material constraint without adding,
omitting, or shifting meaning.

**Gap criteria:** The unit requires guessing the author's intent, omits a
material constraint, introduces a new assumption, or shifts a constraint's
meaning.

**Gap output:** `P1 — semantic drift: {what shifted or requires guessing}`

## P2 — Negative Coverage

**Applies when:** The unit states a boundary, exclusion, invariant, scope
limit, or rejection rationale.

**Checks:** Can at least one concrete implementation that violates the unit be
named?

**Pass:** At least one non-compliant implementation can be clearly
distinguished from a compliant implementation.

**Gap criteria:** No concrete violation can be named because the unit's
boundary is too vague.

**Gap output:** `P2 — boundary unclear: {why compliance cannot be distinguished}`

## P3 — Logical Derivability

**Applies when:** The unit reaches a conclusion that depends on earlier
chapters.

**Checks:** Can the conclusion be independently derived from the earlier
chapters identified by the Method?

**Pass:** The earlier chapters provide a derivation that reaches the same
conclusion.

**Gap criteria:** The derivation is absent or reaches a different conclusion.

**Gap output:** `P3 — logic chain broken: {where derivation diverges}`

## P4 — Boundary Completeness

**Applies when:** The unit describes behavior, a phase, or a task with edge
conditions, failure paths, or conflicting constraints.

**Checks:** Can one difficult boundary case be answered from this unit alone?

**Pass:** The unit gives a clear answer for at least one applicable boundary
case.

**Gap criteria:** The answer is missing, ambiguous, or requires information
outside the unit.

**Gap output:** `P4 — boundary unanswerable: {case and missing information}`

## P5 — Interpretation Determinacy

**Applies when:** A unit defines a data schema, configuration shape,
interface or capability set, state or responsibility ownership, or
cross-module boundary that affects an external contract, acceptance, or an
implementation boundary.

**Checks:** Can two materially different interpretations both satisfy the
unit's explicit wording?

**Pass:** B selects one interpretation with an explicit discriminator, or
explicitly permits multiple interpretations and defines their selection,
compatibility, and acceptance rules.

**Gap criteria:** At least two materially different interpretations conform to
B, and B neither selects one nor defines a controlled multi-option contract.
Differences only in naming, prose, style, or internal implementation freedom do
not qualify.

**Gap output:** `P5 — contract underdetermined: {candidate A} and {candidate
B} both conform but differ in {contract, acceptance, or implementation impact};
missing {decision or multi-option rule}`
