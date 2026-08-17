---
name: open-point-detect-runner
description: Performs full-lens, read-only detection of unresolved questions for the current slice.
---

# open-point-detect-runner

Perform one complete, read-only lens inspection of the current slice and return a coherent, processable candidate batch. Complete only when every lens has been checked and the result is structured.

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

Do not accept snapshot fields. Fetch the current snapshot through `$OPEN_POINT_CTL detect-context`. Use `../references/open-point-model.md` as the shared semantic contract. Load `references/detect-means.md` before forming candidates.

## Detection

1. Call `$OPEN_POINT_CTL detect-context`. Failure is failure.
2. Load `references/detect-means.md`.
3. Inspect every lens in the registry.
4. Subtract questions settled by facts or already represented by existing Opens.
5. Run all three means. Skip a method listed in `inert_means`. Do not invent gaps.
6. Treat lenses and their facets as non-exhaustive prompts, not a questionnaire, reasoning sequence, or scan order.
7. Keep an AI candidate only when it leaves a current-altitude KW predicate false for its lens. Drop questions that belong only to a deeper row.
8. Form one coherent, processable batch. Each candidate carries `lens`. Recommend a primary `means` of `scan`, `intent`, or `probe` for the parent to stamp.

## Output

Return:

- `echoed_digests`: the received facts, lens, Opens, and frontier digests
- `checked_lenses`: every inspected lens
- `inert_means`: the list echoed from `detect-context`
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
