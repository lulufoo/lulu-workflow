# Codebase Consistency SoT

**Role:** EvalSoT template for the `codebase-consistency` dimension.

## Runtime Bindings

- `codebase_root`: repository-relative or absolute root of the code evidence.
- `read_strategy`: code evidence retrieval strategy. The current supported value
  is `all`, meaning inspect files narrowly as claims require.

## Evidence Rules

1. Treat the code under `codebase_root` as the evidence basis.
2. Prefer the defining module, exported interface, schema, or test closest to
   the claim under review.
3. Quote the verified code location and excerpt in every finding.
4. Do not infer implementation details from filenames alone.
