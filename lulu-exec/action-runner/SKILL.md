---
name: action-task-runner
description: >-
  Single-task action executor for lulu-workflow /code sessions.
  Invoked when kind is action. Output: TASK_COMPLETE or TASK_FAILED.
disable-model-invocation: true
---

# action-task-runner

Reach the task goal and answer every acceptance criterion with evidence. Done when `$TC_RECEIPT` and `$TC_DONE` both succeed.

## Blocking policy

If the workflow cannot advance: **stop**, report `TASK_FAILED`, and wait.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../_runtime.md`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/lulu-exec`

## Script Macros

| Macro | Command |
|-------|---------|
| `$TC_CTX` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" resolve-context --task-id <task_id>` |
| `$TC_RECEIPT` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" record-receipt --task-id <task_id>` — stdin: JSON list of `{"criterion", "evidence", "met"}` |
| `$TC_DONE` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" mark-done --task-id <task_id>` |

## Steps

1. Run `$TC_CTX`. Pin `$CTX`. cwd is `$CTX.worktree_abs_path`.
2. Read `$CTX.work_order_task_path`. Reach `$CTX.goal` by whatever means fit, inside `$CTX.effects`:
   - `read_only`: write to no system.
   - `mutates: <systems>`: write only to the named systems.
3. Stay idempotent:
   - Inspect the current state first. Act only on what is missing.
   - Treat work as already done only when the target system shows it (an id, a link, an existing record), not when an earlier run is remembered.
   - If the goal cannot be reached without repeating an effect, stop with `TASK_FAILED`.
4. For each entry of `$CTX.acceptance`, collect evidence a reader can check: an id, link, command output, or count. A criterion without evidence is unmet → `TASK_FAILED`.
5. Run `$TC_RECEIPT` with one result per acceptance entry. `criterion` is copied from `$CTX.acceptance`; `met` is `true`.
6. Run `$TC_DONE`.
7. Output `TASK_COMPLETE <task_id>`.

The receipt script checks that every criterion has non-empty evidence. It cannot check that the evidence is true, so write evidence that a reviewer can sample against the target system.

Repository files are not an action's output. Do not write receipt files by hand. Do not commit.
