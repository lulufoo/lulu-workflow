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

### WriteTests

**Entry:** Append `enter · WriteTests` to `tasks/t{X}/code-log.md`. Set `current_phase: WriteTests`.

**Actions:**

1. Write all test files for the current task. Do not create or modify any implementation files.
2. Use `code.test_command` from `workflow-config.json` for all test runs.

**Exit:** All test files written, no implementation changed → agent auto-advances to `VerifyRed`.

---

### VerifyRed

**Entry:** Append `enter · VerifyRed` to `code-log.md`. Set `current_phase: VerifyRed`.

**Actions:**

1. Run tests; append `test_run` entry to `code-log.md` with full output in fenced block.

**Exception:** If all tests pass unexpectedly → **STOP**. Report: tests have no constraining power over the implementation. Do not advance until resolved.

**Exit:** `test_run` log has at least one FAIL → agent auto-advances to `WriteImpl`.

---

### WriteImpl

**Entry:** Append `enter · WriteImpl` to `code-log.md`. Set `current_phase: WriteImpl`.

**Actions:**

1. Write minimal implementation to make failing tests pass. Do not modify any test files.

**Exit:** Implementation written, no test files modified → agent auto-advances to `VerifyGreen`.

---

### VerifyGreen

**Entry:** Append `enter · VerifyGreen` to `code-log.md`. Set `current_phase: VerifyGreen`.

**Actions:**

1. Run tests; append `test_run` entry to `code-log.md` with full output.
2. On all PASS: append `git_commit · initial` to `code-log.md`; execute `git commit` using `code.git.commit_message_template`; record `tasks/t{X}/commit-ref.md`:
   ```markdown
   task_id: t{X}
   branch: wt/feat-<slug>
   initial_commit: <sha>
   final_commit: <sha>
   commit_message: "<message>"
   amended: false
   recorded_at: <ISO8601>
   ```
3. If `tdd_exempt` is set on this task (from task list or task frontmatter): advance directly to `Done`, skipping Refactor entirely.

**Exception:** Any FAIL → **STOP**. Report failures; do not advance until all tests pass.

**Exit:** All PASS + initial commit written → advance to `Refactor` (or `Done` if `tdd_exempt`).

---

### Refactor

**Entry:** Append `enter · Refactor` to `code-log.md`. Set `current_phase: Refactor`.

**Actions:**

1. Apply behavior-neutral code cleanup. Do not modify test files.
2. Re-run tests after each change; append `test_run` entry to `code-log.md`.
3. If any code changed: append `git_commit · amend` to `code-log.md`; execute `git commit --amend`; update `commit-ref.md` (`final_commit`, `amended: true`). Amend keeps task atomicity — Refactor is part of the same task, not a separate commit.
4. If no changes: skip step 3.

**Exception:** Test regression → **STOP**. Revert change before proceeding.

**Exit:** No behavior change + tests still PASS (or no changes made) → advance to `Done`.

---

### Done

**Entry:** Append `enter · Done` to `code-log.md`. Set `current_phase: Done`.

**Actions:**

1. Mark task `[x]` in `code-task-list.md`.
2. Verify all three exit contract conditions before returning:
   - ① `tasks/t{X}/commit-ref.md` exists with non-empty `initial_commit`
   - ② `tasks/t{X}/code-log.md` contains `enter · Done`
   - ③ `code-task-list.md` has this task marked `[x]`

   These are **preconditions for completion**, not post-conditions. Do not proceed until all three are confirmed.

**Batch commit anti-pattern (prohibited):** Never commit changes for multiple tasks in a single `git commit`. Each task — including `tdd_exempt` tasks and documentation-only changes — must produce its own commit and its own `tasks/t{X}/commit-ref.md`.

---

## Supporting: code-log action model

**Format:** `### <ISO8601> · <action>[ · <target>]` + optional body. **Append-only.**

`code-log.md` is **task-level** only. Session artifacts (`workspace.json`, `closing-checklist.md`, gate) are separate files.

| action | target | meaning |
|--------|--------|---------|
| `enter` | phase name | phase transition |
| `test_run` | — | run `code.test_command`; full output in fenced block |
| `git_commit` | `initial` \| `amend` | commit; SHA and message in body |

No `red-run` / `green-run` action types or standalone red/green files.

`workflow-state.md` is authoritative; use full `Write` for updates; preserve `mode`, `task_list_ref`, `current_task`, `current_phase`.

---

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
