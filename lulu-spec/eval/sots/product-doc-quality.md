# Product Document Quality SoT

**Role:** EvalSoT template for `lulu-spec` dimension `product-doc-quality`.

## Runtime Bindings

- `source_ref`: absolute or project-root-relative path to the upstream
  `decision-doc`.

## Evidence Rules

1. Read `source_ref` as the approved product scope and goal basis.
2. Use it only for the Decision Traceability dimension; the other PDQA
   dimensions evaluate the internal quality of EvalTarget B.
3. Record a finding when B silently expands or contradicts the decision scope.
