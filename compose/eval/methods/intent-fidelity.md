# Intent Fidelity Method

**Role:** EvalMethod template for Compose common dimension `intent-fidelity`.

Absorbs the former `lulu-design` `intent-alignment` checks (GAP / GHOST /
Semantic Consistency) and applies them to every delivery Compose stage.

## Boundary

Evaluate the written delivery document **B** against SoT **A**. A is the
intent baseline at `sots[].ref` from `resolved-refs.intent_baseline_refs`.
Do not read facts, Opens, intent demands, or legacy provenance traces.

When `intent_baseline_refs` is an explicit empty array, Control skips this
dimension for the round. A non-empty array with a missing, unreadable, or
escaping path is malformed input, not a skip.

## Evidence

1. Read every A document as the product-visible intent basis.
2. Intent units include features, boundary values, error handling,
   interaction constraints, and data-format constraints.
3. Quote the A passage and the B location for every finding.
4. If a finding cannot be located in both A and B, do not guess; classify
   it as `UNRESOLVABLE`.

## Procedure

### Axis 1 — Overreach and conflict

For each material, product-visible commitment in B:

- Same theme as A but beyond what A expressed → `扩充意图`.
- No upstream intent source in A → `新增意图` (former GHOST).
- Semantic conflict with A (numeric, behavioral, or naming) → `不一致`
  (former Semantic Consistency).

Do not record general technical infrastructure or documented error-boundary
fallbacks as `新增意图`.

### Axis 2 — Coverage

Enumerate every intent unit in A. If the whole of B neither fulfills it nor
records an auditable explicit disposition → `未履行意图` (former GAP).

## Severity

- Core missing product coverage or a conflicting core commitment: `critical`.
- Material non-core coverage or behavior deviation: `medium`.
- Naming-only deviation: `minor`.

## Taxonomy

Map buckets onto existing `root_cause` values from evidence:

- Valid A not reflected in B → `WO-MISS`.
- B violates valid A or is itself wrong → `WO-ERROR`.
- A missing, ambiguous, or contradictory → `SOT-DEFECT`.
- Evidence insufficient → `UNRESOLVABLE`.
- Confirmed material multi-solution → `DECISION-REQUIRED`.
