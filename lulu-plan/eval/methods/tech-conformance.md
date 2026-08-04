# Tech Conformance Method

**Role:** EvalMethod template for `lulu-plan` dimension `tech-conformance`.

## Boundary

Evaluate EvalTarget **B** against the upstream technical intent supplied by the
paired SoT template. B is a `tech-doc`; the bound upstream document is either a
`design-doc` or a `decision-doc`.

## Procedure

### P1 — Decision and Direction Coverage

For each upstream design decision or direction choice, locate where B
operationalizes it. Record an issue when B omits it or defers it without reason.

### P2 — Constraint Operationalization

For each upstream technical, architectural, or scope constraint, verify that B
reflects it and does not violate it.

### P3 — Acceptance Traceability

When the bound upstream document is a `design-doc`, verify that every
Acceptance Criterion has an explicit task or verification counterpart in B.

### P4 — No Scope Inflation

Record a finding when B introduces a significant implementation decision that
has no upstream basis and materially expands or contradicts the intended scope.

## Severity

- Major missing direction, violated constraint, or missing Acceptance Criterion:
  `critical`.
- Material scope inflation or a peripheral P1/P2/P3 issue: `medium`.
