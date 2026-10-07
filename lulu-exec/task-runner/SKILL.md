---
name: code-task-runner
description: >-
  Single-task TDD executor. Output: TASK_COMPLETE or TASK_FAILED.
disable-model-invocation: true
---

# code-task-runner

Run one coding task through TDD. Done when `$TC_DONE` succeeds and the parent receives `TASK_COMPLETE` with `final_commit`.

## Blocking policy

If the workflow cannot advance: **stop**, report `TASK_FAILED`, and wait. Any `$MACRO` non-zero exit → `TASK_FAILED`. Do not continue the phase loop.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../_runtime.md`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/lulu-exec`

## Script Macros

| Macro | Command |
|-------|---------|
| `$TC_TASK_CTX` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" resolve-context --task-id <task_id>` |
| `$TC_PHASE` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" enter-phase --task-id <task_id> --phase <phase>` |
| `$TC_TESTS` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" run-tests --task-id <task_id> --expect <expect>` |
| `$TC_COMMIT_INIT` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" commit-initial --task-id <task_id>` |
| `$TC_COMMIT_AMEND` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" commit-amend --task-id <task_id>` |
| `$TC_DONE` | `python3 "$SKILL_DIR/scripts/tc_task_control.py" --cycle-dir "<cycle_dir>" mark-done --task-id <task_id>` |

Subcommand contracts: module docstring / `--help`.

## Steps

1. Run `$TC_TASK_CTX`. Pin `$TASK_CTX`. cwd is `$TASK_CTX.worktree_abs_path`.
2. **WriteTests.** `$TC_PHASE` `WriteTests`. Read `$TASK_CTX.work_order_task_path`. Write tests only.
3. **VerifyRed.** `$TC_PHASE` `VerifyRed`. `$TC_TESTS` `--expect red`.
4. **WriteImpl.** `$TC_PHASE` `WriteImpl`. Minimal implementation. Do not modify test files.
5. **VerifyGreen.** `$TC_PHASE` `VerifyGreen`. `$TC_TESTS` `--expect green`. `$TC_COMMIT_INIT`. Keep `final_commit`. If `$TASK_CTX.tdd_exempt`, `$TC_DONE` → `TASK_COMPLETE <task_id> sha=<final_commit>`.
6. **Refactor.** `$TC_PHASE` `Refactor`. Behavior-neutral cleanup. Do not modify test files. `$TC_TESTS` `--expect green`. `$TC_COMMIT_AMEND`. `$TC_DONE`.
7. Output `TASK_COMPLETE <task_id> sha=<final_commit>` from `$TC_COMMIT_INIT` or `$TC_COMMIT_AMEND`.

Do not write session artifacts by hand.
