# Codebase Consistency Method

**Role:** EvalMethod template for the `codebase-consistency` dimension.

## Boundary

Evaluate the delivered EvalTarget **B** against the codebase evidence supplied
by the paired Codebase Consistency SoT template. Inspect only code needed to
verify an explicit claim in B.

## Procedure

1. Read B and the resolved SoT bindings.
2. Identify explicit code claims in B: module paths, symbols, interfaces,
   schemas, conventions, or structural assertions.
3. For each claim, inspect the narrowest relevant code evidence under the
   bound codebase root.
4. Record a finding when a claim is missing from code, contradicts code, or
   misstates a verified convention or boundary.
5. Do not create a finding for a B unit that makes no explicit code claim.

## Finding Contract

Use `WO-MISS` when B omits a required code-grounded concern supplied by the
dimension scope. Use `WO-ERROR` when B makes a false or contradictory code
claim. Cite the code evidence and the Method/SoT template criterion.
