---
name: lulu-tasks
description: >-
  Split a delivered plan into an independently executable task-dependency list.
disable-model-invocation: true
---

# tasks-workflow

Split a delivered plan into an independently executable task-dependency list.

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-tasks`
- Feature identification from `## Session Foundation`
</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_START` | `python3 "$SKILL_DIR/scripts/tt_start.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID" --tech-ref "<tech_ref>"` |
| `$TT_FLOW` | `python3 "$SKILL_DIR/scripts/tt_workflow_control.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$TT_CTX` | `$TT_FLOW resolve-context` |

Subcommand contracts: module docstring / `--help`.

## Start

1. Identify the active cycle through `_runtime.md` § Session Foundation. Do not run `$TT_START` until `$CYCLE_ID` is confirmed.
2. Feature: pass the delivered plan path from the current conversation as `--tech-ref`. Topic: ask for that absolute path.
3. Run `$TT_START`. A non-zero result is Blocking.
4. Run `$TT_CTX` and pin the JSON as `$CTX`.

## Router

Load the unit named by `$CTX.unit`:

- `drafting` → `$SKILL_DIR/references/drafting.md`
- `evaluating` → `$SKILL_DIR/references/evaluating.md`
- `delivery` → `$SKILL_DIR/references/delivery.md`

When a unit returns, run `$TT_CTX` again and load the unit it names. `current_state` `Delivered`: stop.
