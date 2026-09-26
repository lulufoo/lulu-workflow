---
name: open-point-detect-runner
description: Performs full-lens, read-only detection of unresolved questions for the current slice.
---

# open-point-detect-runner

## Goal

Expose unresolved questions that matter to the current slice as one
candidate batch.
`$CTX.guide.cognitive_frame` (D1) and `$CTX.guide.intent_anchor` (D2)
jointly guide Detect as a whole.

## Script Macros

Entry points. Contract in `--help`.

| Macro | Command |
|---|---|
| `$OPEN_POINT_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/open-point/open_point_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

## Inputs

Parent invoke arguments only.

- `--out-dir` and `--project-root` are required.

## Detection context

Slice materials from the two control commands.

1. `$CTX` is `$OPEN_POINT_CTL detect-context` stdout, the roster:
   `opens_snapshot`, `pending_lenses`, and `guide`.
2. `$CTX.guide` is this stage's Domain `cognitive_frame` (D1) and
   `intent_anchor` (D2).
3. `pending_lenses` names the lenses on this pass, not a scan order.
4. `$OPEN_POINT_CTL detect-lens-context --lens <key>` is one lens
   packet: `kw_criteria`, `lens_registry`, and `facts_snapshot`.

## Cognition

Packet terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| `facts_snapshot`, fact | `../../references/cognition/fact.md` |
| `lens_registry`, lens | `../../references/cognition/lens.md` |
| `kw_criteria` | `../../references/cognition/kw-ruler.md` |
| `$CTX.guide` (D1, D2) | `../../references/cognition/profile/domain.md` |
| unknown, candidate Open | `../../references/cognition/producer/induce.md` |

One Detect pass composes them per lens:

```text
candidates(lens) = Detect(lens; kw rows, facts)
                   − SettledBy(facts)
                   − RepresentedBy(opens_snapshot)
```

## Detection dimensions

Rulers for judgment. Question type lives in `references/detect-means.md`.

1. Completeness obligation is the `kw_criteria` rows in the lens packet.
2. `gap_kw` names the coarsest `kw_criteria` row the facts cannot state.

## Boundaries

Invariants for this pass.

- Read-only. Control calls: `detect-context` once; `detect-lens-context`
  once per `pending_lenses` key. A failed fetch fails the pass. Run no
  control command beyond these two.
- Evidence closure: the two control stdout payloads, this SKILL,
  `references/detect-means.md`, and the five Cognition units are the
  whole evidence for one Detect pass. Read nothing outside the closure.
  An unclear term is judged from the closure, not looked up.
- Do not produce options, leanings, or solutions.

## Return

Hand-back shape. `means` is stamped per `references/detect-means.md`.

- One object: one verdict per `pending_lenses` key.
- `gap_kw` is null exactly when `candidates` is empty.

```json
{
  "verdicts": [
    {"lens": "CTX", "gap_kw": 1, "candidates": [
      {
        "question": "What is the current rollback path?",
        "basis": "KW1 is silent on failure recovery",
        "blocking": true,
        "means": "probe"
      }
    ]},
    {"lens": "GO", "gap_kw": null, "candidates": []}
  ]
}
```
