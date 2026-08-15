# Product Document Quality Method

**Role:** EvalMethod (M) for `lulu-spec` dimension `product-doc-quality`.

## Boundary

Audit EvalTarget **B** (`product-doc.md`) at product altitude against SoT **A**
(the twelve PDQA criteria). Do not require or accept implementation detail such
as file paths, APIs, stack choices, test commands, ownership tables, or
implementation order.

Do not read a live `decision-doc`. A is only the twelve criteria.

## Evidence

1. Apply every criterion in A to B.
2. For criterion 8, judge only from B. If B has no citable decision basis and
   the criterion cannot be decided, record `UNRESOLVABLE`.

## Procedure

1. Evaluate each of the twelve criteria independently.
2. Perform one open-ended final read of B after the twelve.
3. Prioritize findings in this order: decision traceability, opening arc,
   acceptance closure, scope protectors, internal consistency; then prose
   polish.
