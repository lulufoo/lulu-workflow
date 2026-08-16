# Norm Conformance Method

**Role:** EvalMethod template for Compose common dimension `norm-conformance`.

## Boundary

Evaluate the written delivery document **B** against SoT **A**. A is the
normative constraint set at `sots[].ref` from
`resolved-refs.norm_constraint_refs`. Do not read facts, Opens, or legacy
provenance traces.

When `norm_constraint_refs` is an explicit empty array, Control skips this
dimension for the round. A non-empty array with a missing, unreadable, or
escaping path is malformed input, not a skip.

Norms are prohibitions, not a to-do list. There is no axis-2 “missing
norm” finding.

## Evidence

1. Read every A document as a constraint set.
2. Quote the A passage and the B location for every finding.
3. If a finding cannot be located in both A and B, do not guess; classify
   it as `UNRESOLVABLE`.

## Procedure

### Axis 1 — Violation

For each constraint in A, check whether B violates it. Record a violation
as `违反`.

There is no axis 2.

## Severity

- Violation of a core constraint: `critical`.
- Material non-core violation: `medium`.
- Naming-only deviation: `minor`.

## Taxonomy

Map buckets onto existing `root_cause` values from evidence:

- B violates valid A or is itself wrong → `WO-ERROR`.
- A missing, ambiguous, or contradictory → `SOT-DEFECT`.
- Evidence insufficient → `UNRESOLVABLE`.
- Confirmed material multi-solution → `DECISION-REQUIRED`.
