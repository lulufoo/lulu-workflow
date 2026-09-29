---
name: verify-task-runner
description: >-
  Single-task verify executor for lulu-workflow /code sessions.
  Invoked when kind is verify. Output: TASK_COMPLETE or TASK_FAILED.
disable-model-invocation: true
---

# verify-task-runner

Run the stated check on the bound worktree. Do not change code. Do not enter the TDD phase chain.

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
| `$TC_CTX` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" --project-root "<project_root>" resolve-context --task-id <task_id>` |
| `$TC_RECEIPT` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" --project-root "<project_root>" record-receipt --task-id <task_id> --command "<command>" --observed "<observed>"` |
| `$TC_DONE` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" --project-root "<project_root>" mark-done --task-id <task_id>` |

## Steps

1. Run `$TC_CTX`. Pin `$CTX`. cwd for the check is `$CTX.worktree_abs_path`.
2. Read `$CTX.work_order_task_path`. Run the named command. Compare to the named observable result.
3. If the result does not match → `TASK_FAILED`.
4. Run `$TC_RECEIPT` with the command and the observed result.
5. Run `$TC_DONE`.
6. Output `TASK_COMPLETE <task_id>`.

Do not write receipt files by hand. Do not commit.
