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
| `$OPEN_POINT_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/open-point/open_point_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

Use the control's `--help` as the command and stdout contract.

## Inputs

Parent supplies invoke arguments only.

- `--out-dir` is required.
- `--project-root` may be empty.
- Fetch the roster through `$OPEN_POINT_CTL detect-context`.

## Principles

1. A candidate is one unresolved question that matters to the current
   slice. Questions settled by this lens's `facts_snapshot` or
   represented in `opens_snapshot` are not candidates.
2. The per-lens `lens_registry` row is a non-exhaustive prompt, not a
   questionnaire. Follow the available evidence; do not invent gaps.
   Coverage order is `frontiers.lenses`.

## Detection

1. Fetch `$OPEN_POINT_CTL detect-lens-context --lens <key>` for every
   key in `frontiers.lenses`, batched in one message.
2. Judge one lens at a time in `frontiers.lenses` order: detect gaps
   against that lens's `kw_criteria`, measured from that lens's
   `frontiers` start, with the methods and evidence scopes in
   `references/detect-means.md`. Conclude the lens's verdict before
   the next lens.
3. A lens is complete when its remaining `kw_criteria` rows are judged
   against its payload. The pass is complete when every lens has a
   verdict.
4. Each candidate carries a recommended primary `means` for the parent
   to stamp.

## Return

- One object after complete lens coverage: one verdict per
  `frontiers.lenses` key.
- `gap_kw` is the coarsest remaining KW predicate left false, or null
  when none — null exactly when `candidates` is empty.
- `means` is `scan`, `intent`, or `probe`.

```json
{
  "verdicts": [
    {"lens": "CTX", "gap_kw": 0, "candidates": [
      {
        "question": "What is the current rollback path?",
        "basis": "KW0 is silent on failure recovery",
        "blocking": true,
        "means": "probe"
      }
    ]},
    {"lens": "GO", "gap_kw": null, "candidates": []}
  ]
}
```

## Boundaries

- Read-only. Control calls: `detect-context` at Input;
  `detect-lens-context` once per `frontiers.lenses` key.
- Evidence closure: the two control stdout payloads, this SKILL, and
  `references/detect-means.md` are the whole evidence for one Detect
  pass.
- Do not produce options, leanings, or solutions.
