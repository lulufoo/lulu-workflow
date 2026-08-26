---
name: open-point-detect-runner
description: Performs full-lens, read-only detection of unresolved questions for the current slice.
---

# open-point-detect-runner

## Goal

Expose unresolved questions that materially affect the current slice as
one coherent, processable candidate batch.

## Preconditions

- Read `references/detect-means.md`.

## Script Macros

| Macro | Command |
|---|---|
| `$OPEN_POINT_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/open_point_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

Use the control's `--help` as the command and stdout contract.

## Inputs

Parent supplies invoke arguments only.

- `--out-dir` is required.
- `--project-root` may be empty.
- Fetch the snapshot through `$OPEN_POINT_CTL detect-context`.

## Principles

1. A candidate is one unresolved question that matters to the current
   slice. Questions settled by `facts_snapshot` or represented in
   `opens_snapshot` are not candidates.
2. Lenses in `lens_registry` are non-exhaustive prompts, not a
   questionnaire or scan order. Follow the available evidence; do not
   invent gaps.

## Detection

1. For every lens in `lens_registry`, detect gaps against its coarsest
   remaining KW in `kw_criteria`, measured from that lens's `frontiers`
   start.
2. Use the methods and evidence scopes in `references/detect-means.md`.
3. Preserve complete inspection evidence: per-lens measurements and raw
   outcome.
4. Form one coherent, processable batch. Each candidate carries `lens`
   and a recommended primary `means` for the parent to stamp.

## Return

- One object after complete lens coverage.
- `means` is `scan`, `intent`, or `probe`.
- Empty detection uses `candidates: []`.

```json
{
  "checked_lenses": ["CTX", "GO"],
  "lens_measurements": [
    {"lens": "CTX", "start_kw": 0, "gap_kw": 0},
    {"lens": "GO", "start_kw": 0, "gap_kw": null}
  ],
  "candidates": [
    {
      "question": "What is the current rollback path?",
      "basis": "KW0 is silent on failure recovery",
      "blocking": true,
      "lens": "CTX",
      "means": "probe"
    }
  ]
}
```

## Boundaries

- Read-only. The only control call is `$OPEN_POINT_CTL detect-context`.
- Do not produce options, leanings, or solutions.
