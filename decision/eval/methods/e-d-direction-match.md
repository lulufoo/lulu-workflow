# Method — E↔D direction match

## Pair

- `<!-- chapter:direction -->` (from `gate-payloads/E.json`)
- `<!-- chapter:settled_direction -->` (from `gate-payloads/D.json`)

## Check

Does E `user_choice` (and the chosen direction summary) describe the **same path** as D `decision_rationale` / `execution_approach`?

## Blocker

Emit a review issue when they diverge. Set `location` to the mismatched chapter/field. Disposition routing uses `realign_gate=E` (Decision Eval → RS; do not edit EvalTarget).
