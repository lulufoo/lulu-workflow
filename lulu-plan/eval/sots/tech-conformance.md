# Tech Conformance SoT

**Role:** EvalSoT template for `lulu-plan` dimension `tech-conformance`.

## Runtime Bindings

- `source_ref`: absolute or project-root-relative path to the upstream
  `design-doc` or `decision-doc`.

## Evidence Rules

1. Read `source_ref` as the complete upstream technical intent basis.
2. A `design-doc` supplies decisions, constraints, and Acceptance Criteria.
3. A `decision-doc` supplies directions and constraints but no Acceptance
   Criteria to trace.
4. Quote upstream passages when recording a conformance finding.
