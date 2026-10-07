---
name: lulu-exec
description: >-
  Execute a delivered work order to a committed worktree delivery or an evidenced action receipt.
disable-model-invocation: true
---

# code-workflow

Execute a delivered work order by task `kind`. Done when `$TC_CTX` reports `unit` `delivered`.

A non-zero `$MACRO` is Blocking: stop, report, wait.

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-exec`
- Feature identification from `## Session Foundation`
</HARD-GATE>

## Script Macros

| Macro | Command |
|-------|---------|
| `$TC_START` | `python3 "$SKILL_DIR/scripts/tc_start.py" --cycle-id "$CYCLE_ID"` |
| `$TC_FLOW` | `python3 "$SKILL_DIR/scripts/tc_session_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID"` |
| `$TC_CTX` | `$TC_FLOW resolve-context` |

Subcommand contracts: module docstring / `--help`.

## Start

1. Identify the active cycle through `_runtime.md` § Session Foundation. Do not run `$TC_START` until `$CYCLE_ID` is confirmed.
2. Run `$TC_CTX` and pin the JSON as `$CTX`.
3. If `$CTX.unit` is `starting`, run `$TC_START`, then `$TC_CTX` again.
4. If `$CYCLE_TYPE` is `topic` and `$CTX.unit` is `executing` or `closing`, announce `$CTX.current_state` / `$CTX.current_task` and ask to resume. **No** → `$TC_START`, then `$TC_CTX`. Feature containers auto-resume.

## Router

Load the unit named by `$CTX.unit`:

- `preparing` → `$SKILL_DIR/references/preparing.md`
- `executing` → `$SKILL_DIR/references/executing.md`
- `closing` → `$SKILL_DIR/references/closing.md`
- `delivered` → stop
- `starting` → ## Start

When a unit returns, run `$TC_CTX` again and load the unit it names.
