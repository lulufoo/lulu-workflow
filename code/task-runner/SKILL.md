---
name: code-task-runner
description: >-
  Single-task TDD executor for lulu-dev-workflow /code sessions.
  Invoked by the parent code/SKILL.md orchestrator per task.
  Input: task spec + worktree path. Output: commit-ref.md + code-log.md + task marked [x].
  Use when: dispatched by code/SKILL.md Executing loop for a single task.
meta-skill-version: 1.0.0
---

# code-task-runner

Sub-agent executing a single TDD task within a lulu-dev-workflow /code session.
Runs WriteTests → VerifyRed → WriteImpl → VerifyGreen → Refactor → Done.
Commits after VerifyGreen; amends after Refactor if code changed.

## Input Contract

Received via the invocation prompt (structured as shown in code/SKILL.md Task loop step 1):

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | string | e.g. `t1` |
| `worktree_abs_path` | string | Absolute path to the worktree directory for this task |
| `code_task_list_path` | string | Absolute path to `code-task-list.md` |
| `commit_message_template` | string | From `workflow-config.json code.git.commit_message_template` |
| task spec | markdown content | Full content of `task.md` (acceptance criteria, constraints, function specs) |

All file edits and test runs operate inside `worktree_abs_path`.

## Execution

Execute TDD phases in order: WriteTests → VerifyRed → WriteImpl → VerifyGreen → Refactor → Done.

**Phase specifications are authoritative in `$SKILL_ROOT/code/SKILL.md` `## Executing` section.**
Read `code/SKILL.md` for each phase's entry actions, exit conditions, and exception handling.
Apply the same rules here without modification.

## Exit Contract

Before returning, verify all three conditions:

1. `tasks/{task_id}/commit-ref.md` exists with non-empty `initial_commit` SHA
2. `tasks/{task_id}/code-log.md` contains `enter · Done`
3. `{task_id}` is marked `[x]` in `code-task-list.md`

**On success:** output to parent agent:
```
TASK_COMPLETE {task_id} sha={commit_sha}
```

**On failure (any phase exception or unrecoverable test failure):**
1. Write `tasks/{task_id}/error-log.md` with error details
2. Output to parent agent:
```
TASK_FAILED {task_id} reason={brief description}
```
