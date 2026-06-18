---
name: code-task-runner
description: >-
  Single-task TDD executor for lulu-dev-workflow /code sessions.
  Invoked by the parent code/SKILL.md orchestrator per task.
  Input: dispatch coordinates; bootstraps $CTX via task_control resolve-context.
  Output: TASK_COMPLETE or TASK_FAILED.
  Use when: dispatched by code/SKILL.md Executing loop for a single task.
meta-skill-version: 1.0.0
---

# code-task-runner

Sub-agent executing a single TDD task within a lulu-dev-workflow /code session.
Mechanical side effects (log, tests, commit, checkbox) are driven by `task_control.py`.
Agent owns creative work: WriteTests, WriteImpl, Refactor.

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason (`TASK_FAILED`), and **wait** for user direction before continuing.

Any `task_control.py` non-zero exit or phase exception → `TASK_FAILED` + optional `error-log.md`. Do not continue the phase loop.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/tech-code` (from `## Platform Context` in `_runtime.md`)

## Dispatch input

Received as JSON via the invocation prompt `## Input` block:

```json
{
  "task_id":     "<task_id>",
  "cycle_dir":   "<abs_path>/.cache/<platform>/lulu-dev-workflow/<cycle_id>",
  "project_root": "<abs_path>/to/project"
}
```

## Step 0: Resolve context

```bash
python3 "$SKILL_DIR/scripts/tc_task_control.py" \
  --cycle-dir "<cycle_dir>" \
  --project-root "<project_root>" \
  resolve-context --task-id <task_id>
```

Parse stdout JSON as `$CTX`. Required fields include:
`work_order_task_path`, `task_output_dir`, `code_task_list_path`, `worktree_abs_path`,
`branch`, `tdd_exempt`, `commit_message_template`, `test_command`.

<HARD-GATE>
Before any `commit-*` subcommand, load `docs/git/git-workflow-standard.md`.
</HARD-GATE>

All code edits and test runs: cwd = `$CTX.worktree_abs_path`.

## Phase loop

Use this command template for mechanical steps:

```bash
python3 "$SKILL_DIR/scripts/tc_task_control.py" \
  --cycle-dir "<cycle_dir>" \
  --project-root "<project_root>" \
  <subcommand> --task-id <task_id> [args]
```

### WriteTests

1. `enter-phase --phase WriteTests`
2. Read `$CTX.work_order_task_path`; write test files only (no implementation).
3. Continue to VerifyRed.

### VerifyRed

1. `enter-phase --phase VerifyRed`
2. `run-tests --expect red`
3. On non-zero exit → `TASK_FAILED` (unexpected all-PASS).
4. Continue to WriteImpl.

### WriteImpl

1. `enter-phase --phase WriteImpl`
2. Write minimal implementation; do not modify test files.
3. Continue to VerifyGreen.

### VerifyGreen

1. `enter-phase --phase VerifyGreen`
2. `run-tests --expect green`
3. `commit-initial` — parse stdout JSON; keep `final_commit` for `TASK_COMPLETE`.
4. If `$CTX.tdd_exempt` → `mark-done` → `TASK_COMPLETE`.
5. Else continue to Refactor.

### Refactor

1. `enter-phase --phase Refactor`
2. Apply behavior-neutral cleanup; do not modify test files.
3. `run-tests --expect green`
4. `commit-amend` (skips automatically when worktree is clean).
5. `mark-done` → `TASK_COMPLETE`.

## Exit contract

On success, output to parent:

```
TASK_COMPLETE <task_id> sha=<final_commit>
```

Use `final_commit` from `commit-initial` or `commit-amend` stdout JSON.

On failure:

1. Write `$CTX.task_output_dir/error-log.md` with error details.
2. Output:

```
TASK_FAILED <task_id> reason=<brief description>
```

Do not manually write `commit-ref.md`, `code-log.md` entries, or flip `[x]` — `task_control.py` owns those artifacts.
