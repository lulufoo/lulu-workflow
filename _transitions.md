# Stage Transitions

When a stage delivers:
1. Read `$SKILL_ROOT/config/transition-table.json`
2. Collect all entries where `from == <current_stage>` (`null` if no active stage) under the `cycle_type` key (`topic` or `feature`); aggregate their `to` arrays
3. Present all allowed next stages from the `to` array; wait for explicit user selection
4. If `to` is empty: announce completion; display the `note` field if present

> Any transition not listed in `transition-table.json` is **prohibited**.
> The same rules are machine-enforced at stage entry via `check_gate` (`scripts/start_gate.py`).

## Stage Rollback

Any participant may trigger a Stage Rollback when new information shows a prior stage's output is no longer valid:

- **Trigger:** state the target stage to roll back to (any prior stage, any number of levels back)
- **Effect on Product Line:** rolling back to `lulu-bet` invalidates `lulu-spec` + entire tech line; rolling back to `lulu-spec` invalidates entire tech line.
- **Effect on Tech Line:** rolling back to `lulu-approach` invalidates `lulu-plan`, `lulu-tasks`, `lulu-exec`.
- **AI must announce:** "[target stage] and all downstream stages are invalidated. Restarting from [target stage]."
