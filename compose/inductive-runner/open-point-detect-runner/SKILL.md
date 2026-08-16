---
name: open-point-detect-runner
description: Performs full-lens, read-only detection of unresolved questions for the current slice.
---

# open-point-detect-runner

Perform one complete, read-only lens inspection of the current slice and return a coherent, processable candidate batch. Complete only when every lens has been checked and the result is structured.

## Goal

Expose unresolved questions that materially affect the current slice.

## Inputs

Required:

- `facts_snapshot` and `facts_digest`
- `lens_registry` and `lens_digest`
- `existing_open_summaries` and `opens_digest`

Optional:

- intent baseline
- norm constraints
- project evidence scope

Use `../references/open-point-model.md` as the shared semantic contract.

## Detection

1. Inspect every lens in the registry.
2. Subtract questions settled by facts or already represented by existing Opens.
3. Synthesize relevant evidence from code scanning, intent-baseline comparison, and collisions involving failures, boundaries, assumptions, or seams.
4. Treat lenses and their facets as non-exhaustive prompts, not a questionnaire, reasoning sequence, or scan order.
5. Use judgment to form one coherent, processable batch from the unresolved findings.

## Output

Return:

- `echoed_digests`: the received facts, lens, and Opens digests
- `checked_lenses`: every inspected lens
- `candidates`: findings in processing order

Each candidate contains only:

- `question`
- `basis`
- `blocking`

When raw detection finds no candidates, return `candidates: []` explicitly.

## Boundaries

- Remain read-only and stateless.
- Do not interact with the user.
- Do not write facts, Opens, receipts, or gate state.
- Do not decide closure.
- Do not produce options, leanings, or solutions.
- A timeout, exception, or invalid output has no state side effect.

## Return

Return the structured result only after complete lens coverage. Incomplete coverage or invalid structure is a failure, not a partial batch.
