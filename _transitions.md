# Stage Transitions

When a stage delivers:
1. Read `$SKILL_ROOT/config/transition-table.json`
2. Collect all entries where `from == <current_stage>` (`null` if no active stage) under the `cycle_type` key (`topic` or `feature`); aggregate their `to` arrays
3. Present all allowed next stages from the `to` array; wait for explicit user selection (see § Autonomous Tech Line Auto-Chain for the exception)
4. If `to` is empty: announce completion; display the `note` field if present

> Any transition not listed in `transition-table.json` is **prohibited**.
> The same rules are machine-enforced at stage entry via `check_gate` (`scripts/start_gate.py`).

## § Autonomous Tech Line Auto-Chain

**Trigger conditions:** `$EXECUTION_MODE == "autonomous"` AND `cycle_type == "feature"`

**Auto-chain whitelist** (on delivery, immediately start the next stage without user selection):
`tech-plan` → `tech-work-order` → `tech-code`

Does **not** trigger for **Guided mode**.

Each stage's autonomous overrides govern how delivery and handoff are executed. See `Autonomous Overrides` sections in `tech-plan/SKILL.md`, `tech-work-order/SKILL.md`, and `tech-code/SKILL.md`.

---

## Stage Rollback

Any participant may trigger a Stage Rollback when new information shows a prior stage's output is no longer valid:

- **Trigger:** state the target stage to roll back to (any prior stage, any number of levels back)
- **Effect on Product Line:** rolling back to `product-diagnostic` invalidates `product-plan` + entire tech line; rolling back to `product-plan` invalidates entire tech line.
- **Effect on Tech Line:** rolling back to `tech-diagnostic` invalidates `tech-plan`, `tech-work-order`, `tech-code`.
- **AI must announce:** "[target stage] and all downstream stages are invalidated. Restarting from [target stage]."
