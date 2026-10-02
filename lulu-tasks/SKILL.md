---
name: lulu-tasks
description: >-
  Split a delivered plan or approach decision into an independently executable task-dependency list.
disable-model-invocation: true
---

# tasks-workflow

Split a delivered plan, or an approach decision when no plan is delivered, into an independently executable task-dependency list. `tech-doc` in this skill means that reference document.

A task has `kind: coding` or `kind: action`.

- `coding` changes code. Function-count, signatures, TDD order, and `tdd_exempt` apply only to this kind.
- `action` reaches a stated goal by any means. It declares `effects`, lists acceptance criteria that evidence can answer one by one, and binds a worktree only when it names one. It does not commit code.

Delivery starts `lulu-exec` for the whole work order. That session dispatches by `kind`.

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-tasks`
- Feature identification from `## Session Foundation`
</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_START` | `python3 "$SKILL_DIR/scripts/tt_start.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$TT_FLOW` | `python3 "$SKILL_DIR/scripts/tt_workflow_control.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$TT_CTX` | `$TT_FLOW resolve-context` |

Subcommand contracts: module docstring / `--help`.

## Start

1. Identify the active cycle through `_runtime.md` § Session Foundation. Do not run `$TT_START` until `$CYCLE_ID` is confirmed.
2. Run `$TT_START`. It reads the delivered plan, or the delivered approach decision when no plan is delivered, from the cycle's delivered refs. A non-zero result is Blocking.
3. Run `$TT_CTX` and pin the JSON as `$CTX`.

## Router

Load the unit named by `$CTX.unit`:

- `drafting` → `$SKILL_DIR/references/drafting.md`
- `evaluating` → `$SKILL_DIR/references/evaluating.md`
- `delivery` → `$SKILL_DIR/references/delivery.md`

When a unit returns, run `$TT_CTX` again and load the unit it names. `current_state` `Delivered`: stop.
