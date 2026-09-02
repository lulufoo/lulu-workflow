# Scope Continuity Method

**Role:** EvalMethod template for Compose common dimension `scope-continuity`.

## Boundary

Evaluate the written delivery document **B** against SoT **A**. A is the
single readable parent document resolved from `resolved-refs.scope_ref`
for the current focus L. Do not treat a scope-package pointer as natural-
language SoT. Do not read facts, Opens, or legacy provenance traces.

Missing or unreadable `scope_ref` fails admission. This dimension is never
skipped.

## Evidence

1. Read A as the explicit parent-decision basis.
2. Quote the A passage and the B location for every finding.
3. If a finding cannot be located in both A and B, do not guess; classify
   it as `UNRESOLVABLE`.

## Procedure

### Axis 1 — Conflict

Report only a conflict between B and an explicit parent decision in A.
Untraceable lawful refinement or a new branch is not a deviation.

Bucket: `不一致`.

### Axis 2 — Omission

If an explicit parent decision is neither continued, refined, nor explicitly
deferred / sunk in B → `遗漏明确决策`.

## Severity

- Conflict with or omission of a core parent decision: `critical`.
- Material non-core conflict or omission: `medium`.
- Naming-only deviation: `minor`.

## Taxonomy

Map buckets onto existing `root_cause` values from evidence:

- Valid A not reflected in B → `WO-MISS`.
- B violates valid A or is itself wrong → `WO-ERROR`.
- A missing, ambiguous, or contradictory → `SOT-DEFECT`.
- Evidence insufficient → `UNRESOLVABLE`.
- Confirmed material multi-solution → `DECISION-REQUIRED`.
