# Product Design Alignment Method

**Role:** EvalMethod template for `lulu-design` dimension `intent-alignment`.

## Boundary

Evaluate the technical design EvalTarget **B** against the upstream product
baseline supplied by the paired SoT template.

## Procedure

### A — Coverage

Decompose the upstream product baseline into minimal requirement units. For each
unit, locate a covering interface design, data flow, module partitioning, or
boundary condition in B. Record an uncovered unit as `GAP`.

### B — Traceability

For every material design decision in B, identify its upstream product source.
Do not record general technical infrastructure or documented error-boundary
fallbacks as `GHOST`. Record an ungrounded business feature or behavior as
`GHOST`.

### C — Semantic Consistency

Compare upstream and B for numeric, behavioral, and naming deviations. Record
the source passages and describe the deviation precisely.

## Severity

- Core missing product coverage: `critical`.
- Material non-core coverage or behavior deviation: `medium`.
- Naming-only deviation: `minor`.
