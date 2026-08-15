# Tech Conformance Method

**Role:** EvalMethod template for `lulu-plan` dimension `tech-conformance`.

## Boundary

Evaluate EvalTarget **B** against SoT **A**. B is a `tech-doc`. A is the
upstream `design-doc` or `decision-doc` at `sots[].ref`.

## Evidence

1. Read A as the complete upstream technical intent basis.
2. A `design-doc` supplies decisions, constraints, and Acceptance Criteria.
3. A `decision-doc` supplies directions and constraints but no Acceptance
   Criteria to trace.
4. Quote upstream passages when recording a conformance finding.

## Procedure

### P1 — Decision and Direction Coverage

For each upstream design decision or direction choice, locate where B
operationalizes it. Record an issue when B omits it or defers it without reason.

### P2 — Constraint Operationalization

For each upstream technical, architectural, or scope constraint, verify that B
reflects it and does not violate it.

### P3 — Acceptance Traceability

When A is a `design-doc`, verify that every Acceptance Criterion has an
explicit task or verification counterpart in B.

### P4 — No Scope Inflation

Record a finding when B introduces a significant implementation decision that
has no upstream basis and materially expands or contradicts the intended scope.

## Severity

- Major missing direction, violated constraint, or missing Acceptance Criterion:
  `critical`.
- Material scope inflation or a peripheral P1/P2/P3 issue: `medium`.
