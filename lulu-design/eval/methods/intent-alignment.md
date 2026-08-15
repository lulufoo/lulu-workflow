# Product Design Alignment Method

**Role:** EvalMethod template for `lulu-design` dimension `intent-alignment`.

## Boundary

Evaluate the technical design EvalTarget **B** against SoT **A**. A is the
upstream product baseline at `sots[].ref`.

## Evidence

1. Read A as the product requirement basis.
2. Requirement units include features, boundary values, error handling,
   interaction constraints, and data-format constraints.
3. Quote the product baseline passage for every GAP, GHOST, or semantic
   deviation finding.

## Procedure

### A — Coverage

Decompose A into minimal requirement units. For each unit, locate a covering
interface design, data flow, module partitioning, or boundary condition in B.
Record an uncovered unit as `GAP`.

### B — Traceability

For every material design decision in B, identify its upstream product source
in A. Do not record general technical infrastructure or documented
error-boundary fallbacks as `GHOST`. Record an ungrounded business feature or
behavior as `GHOST`.

### C — Semantic Consistency

Compare A and B for numeric, behavioral, and naming deviations. Record the
source passages and describe the deviation precisely.

## Severity

- Core missing product coverage: `critical`.
- Material non-core coverage or behavior deviation: `medium`.
- Naming-only deviation: `minor`.
