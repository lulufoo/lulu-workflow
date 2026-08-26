---
name: open-point-detect-runner
description: Performs full-lens, read-only detection of unresolved questions for the current slice.
---

# open-point-detect-runner

Perform one complete, read-only lens inspection of the current slice and return a coherent, processable candidate batch. Complete only when every lens has been measured from its start and the coarsest remaining gaps are structured.

## Script Macros

| Macro | Command |
|---|---|
| `$OPEN_POINT_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/open_point_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

Use the control's `--help` as the command and stdout contract.

## Goal

Expose unresolved questions that materially affect the current slice.

## Inputs

The parent supplies only invoke arguments:

- `--out-dir`
- `--project-root` (empty is legal)

Do not accept snapshot fields. Fetch the current snapshot through `$OPEN_POINT_CTL detect-context`. Load `references/detect-model.md` and `references/detect-means.md` before forming candidates.

## Detection

1. Call `$OPEN_POINT_CTL detect-context`. Failure is failure.
2. Load `references/detect-means.md`.
3. Inspect every lens in the registry.
4. Subtract questions settled by facts or already represented by existing Opens.
5. Run all three means. Skip a method listed in `inert_means`. Do not invent gaps.
6. Treat lenses and their facets as non-exhaustive prompts, not a questionnaire, reasoning sequence, or scan order.
7. For each lens, start at `frontier_kw`. Keep AI candidates only at that lens's coarsest remaining false KW. Drop finer rows. Several questions at that KW are legal. Return no candidates only when every required unskipped lens has no false KW on its published KW slice from that start.
8. Form one coherent, processable batch. Each candidate carries `lens`. Recommend a primary `means` of `scan`, `intent`, or `probe` for the parent to stamp.

## Output

Return:

- `echoed_digests`: the received facts, lens, Opens, and frontier digests
- `checked_lenses`: every inspected lens
- `inert_means`: the list echoed from `detect-context`
- `lens_measurements`: per checked lens, `start_kw` and `gap_kw` (`null` if none)
- `candidates`: findings in processing order

Each candidate contains only:

- `question`
- `basis`
- `blocking`
- `lens`
- `means` (`scan` | `intent` | `probe`)

When raw detection finds no candidates, return `candidates: []` explicitly.

## Boundaries

- Remain read-only and stateless.
- Do not interact with the user.
- Do not call `ensure-frontier` or `add-opens`.
- Do not write facts, Opens, receipts, or gate state.
- Do not decide closure.
- Do not produce options, leanings, or solutions.
- A timeout, exception, or invalid output has no state side effect.

## Return

Return the structured result only after complete lens coverage. Incomplete coverage or invalid structure is a failure, not a partial batch.
