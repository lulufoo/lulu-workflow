# Intent Gap Probes

**Consumer:** `prober-runner` (Round Iteration — per sub-section diagnostic).

Run the applicable probes against each sub-section. A probe failure is an intent gap — the sub-section lacks a constraint dimension that must be added before the content can be trusted.

---

## P1 — Semantic Fidelity

**Applies when:** Always — apply to every sub-section.

**Checks:** Can the intent of this sub-section be accurately restated without ambiguity?

**Pass:** A restatement of the sub-section's intent matches the original — no key constraint is dropped, added, or shifted in meaning.

**Gap criteria:** The restatement drifts from the original (omits a constraint, introduces a new assumption, or requires guessing the author's intent).

**Gap output:** `P1 — semantic drift: {description of what shifted}`

---

## P2 — Negative Coverage

**Applies when:** The sub-section asserts a boundary, exclusion, or constraint (e.g. a non-goal, invariant, or rejection rationale).

**Checks:** Can at least one concrete violation of this sub-section's intent be enumerated?

**Pass:** At least one implementation approach that would violate this intent can be clearly named.

**Gap criteria:** No concrete violation can be enumerated — the boundary of the intent is too vague to distinguish compliant from non-compliant behavior.

**Gap output:** `P2 — boundary unclear: {what makes violations hard to enumerate}`

---

## P3 — Logical Derivability

**Applies when:** The sub-section draws a conclusion that depends on content from upstream sections (e.g. a decision, approach phase, or task that should follow from goals or constraints).

**Checks:** Can this sub-section's conclusion be independently derived from the upstream sections, without reading this sub-section?

**Pass:** The derivation path exists and leads to the same conclusion.

**Gap criteria:** The derivation diverges from the sub-section's conclusion, or no derivation path exists — the upstream sections do not provide enough constraint to support this conclusion.

**Gap output:** `P3 — logic chain broken: {where the derivation diverges}`

---

## P4 — Boundary Completeness

**Applies when:** The sub-section describes behavior, a phase, or a task that has edge conditions, failure paths, or conflicting constraints.

**Checks:** Can a tricky boundary case be answered using only this sub-section's content?

**Pass:** At least one boundary case (edge condition, error path, or conflicting constraint) can be given a clear, unambiguous answer from this sub-section alone.

**Gap criteria:** The boundary case answer is ambiguous, missing, or requires information not present in this sub-section.

**Gap output:** `P4 — boundary unanswerable: {case description and what is missing}`
