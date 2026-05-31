---
name: code
description: >-
  Use when: TDD, code session, 测试驱动开发, 写测试代码, 写实现代码, Red Green Refactor,
  code-task-list, task-from-work-order, code workflow,
  lulu-dev-workflow code, git worktree delivery.
disable-model-invocation: true
---

# code-workflow

Execute Test-Driven Development from a Delivered work-order task set, with git worktree delivery and per-task commits. **Scope:** TDD code generation in a dedicated worktree. Input: Delivered work-order task set. Output: tests + implementation, per-task `commit-ref.md`, closing checklist, human delivery gate. Session lifecycle: **Preparing → Executing → Closing → Delivered**.

**This workflow runs in Agent mode.** (requires writing code files and executing Shell commands)

**`/code` authorizes** automatic `git commit` / `git commit --amend` inside the session worktree during Executing. Push, PR, CI, and review are post-code (out of scope).

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Feature Context`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/code`

---

## Commands

### `/code <input>` — Entry point

| Format | Meaning | Example |
|--------|---------|---------|
| `work-order/<uuid>` | Source: specified work-order session | `/code work-order/1d2ea64b-065d-4e12-9008-9163d475ee00` |

If the user's input does not match this format, stop and output the usage error.

---

### AI startup sequence (after valid input)

**Step 0: Load `docs/git/git-workflow-standard.md`** — required before any git operations.

**Step 1: Identify active feature** — See `## Feature Context` in `../SKILL.md`

**Step 2–4:** Parse input, validate upstream Delivered state, collect paths.

**Step 5: Run `start.py`** — bootstraps `current_state: Preparing` with empty `current_task` / `current_phase`.

**Step 6:** Read `code-task-list.md`; display tasks; wait for confirmation before execution.

---

## Session files

```
$CACHE_DIR/<feature_id>/code/
  session-state.md
  s{N}/
    workflow-state.md           ← Preparing: session + task pointer (authoritative)
    workspace.json              ← Preparing: worktree_path, branch, created_at
    code-task-list.md           ← Preparing: task list from work-order
    closing-checklist.md        ← Closing: checklist items
    human-delivery-gate.md      ← Closing→Delivered: required before Delivered

    tasks/t{X}/
      code-log.md               ← Executing: append-only action log (task-level)
      commit-ref.md             ← Executing/Done: initial/final SHA, message, amended
```

Do **not** create `red-run.md` or `green-run.md`. Red/Green evidence belongs in `code-log.md` as `test_run` entries.

Optional seed: `$SKILL_DIR/templates/code-log.template.md` (replace `t{X}`).

---

## State machine

**SSOT:** `$SKILL_DIR/transition-whitelist.json` — parallel `session` and `task` machines with `states` enums and `allowed_transitions`. This SKILL documents semantics only; do not duplicate transition tables here.

`transition-whitelist.json` defines which transitions are *allowed*; each state section below defines *when* to trigger — the two are complementary and non-overlapping.

Session states: `Preparing` → `Executing` → `Closing` → `Delivered`

Task phases (under Executing): `WriteTests` → `VerifyRed` → `WriteImpl` → `VerifyGreen` → `Refactor` → `Done`

---

## Preparing

**Entry:** `start.py` sets `current_state: Preparing`. `workflow-state.md` exists.

**Actions:**

**Step 0：task-spec schema 校验（前置门控）**

对 work-order 交付的每个 task.md 执行 schema 校验：
- 检查 frontmatter 是否包含 `target_repo`（非空字符串）
- 检查 frontmatter 是否包含 `task_worktree`（`"primary"` 或合法相对路径）
- 检查 frontmatter 是否包含 `exit_contract`（含 `commit`、`commit_ref_md`、`code_log` 三个 key，值均为 `required`）
- 任一缺失 → 输出具体缺失字段和 task_id，停止执行，等待用户修正
- 检查 `task_worktree` 一致性：同一 target_repo 的所有 task 必须使用相同 task_worktree（不同则报 schema 冲突错误）

1. Read `$WORKFLOW_DIR/workflow-config.json` → `code.git` (`worktree_base`, `branch_pattern`, `default_type`, `commit_message_template`).
2. Derive `<slug>` from feature id or scope; build paths:
   - worktree dir: `{worktree_base}/<slug>/` (default `.cache/worktrees/<slug>/`)
   - branch: apply `branch_pattern` with `{type}` = `default_type` (default `wt/feat-<slug>`)
3. Execute **P1 → P2 → P3** from `git-workflow-standard.md` using the derived `<slug>` and `code.git` config values.
4. Write `s{N}/workspace.json`:
   ```json
   {
     "worktree_path": ".cache/worktrees/<slug>/",
     "primary_repo": "<repo-name>",
     "branch": "wt/feat-<slug>",
     "created_at": "<ISO8601>",
     "extra_worktrees": {
       "<repo-name>": {
         "path": ".cache/worktrees/<slug>-<repo-suffix>/",
         "branch": "wt/feat-<slug>-<repo-suffix>"
       }
     }
   }
   ```
   `extra_worktrees` 仅在存在 target_repo ≠ primary_repo 的 task 时写入，否则省略此字段。

**Exit:** All worktree and branch setup complete, `workspace.json` written → update `workflow-state.md`: `current_state: Executing`, set `current_task` to first runnable task, `current_phase: WriteTests`. All subsequent TDD edits and commits run inside the worktree directory.

---

## Executing

**Entry:** `current_state: Executing`, `current_task` = first runnable task, `current_phase: WriteTests`.

Process tasks 1→N in sequence. Advance `current_phase` only when `current_state` is `Executing`.

### Task loop (1→N)

**Invariant:** Never commit changes for multiple tasks in a single `git commit`. Each task must produce its own commit and its own `tasks/t{X}/commit-ref.md`.

For each task in order:

**Step 1: Dispatch sub-agent**

Read `task.md` → resolve `task_worktree` to `worktree_abs_path`:
- `"primary"` → absolute path of workspace.json `worktree_path`
- relative path → `{project_root}/{task_worktree}` (absolute)

Invoke `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`, prompt:

```
You are executing a single TDD task.
Load $SKILL_ROOT/code/task-runner/SKILL.md and follow its instructions.

## Input
task_id: {task_id}
worktree_abs_path: {worktree_abs_path}
code_task_list_path: {abs_path_to_code-task-list.md}
commit_message_template: {template_from_workflow-config}

## Task Spec
{full content of task.md}
```

**Step 2: Validate exit contract** (after sub-agent returns)

① `tasks/t{X}/commit-ref.md` exists with non-empty `initial_commit`
② `tasks/t{X}/code-log.md` contains `enter · Done`
③ `code-task-list.md` has `t{X}` marked `[x]`

If any check fails → stop, report which check failed, wait for user intervention.
If sub-agent returned `TASK_FAILED` → stop, surface error and reason, wait for user.

**Step 3: CHECKPOINT output**

Output: `CHECKPOINT t{X}: commit SHA <sha>, commit-ref.md written, advancing to t{X+1}.`
Do not advance until this line is output.

**Step 4: Branch**

- More tasks remain → update `current_task` to t{X+1}; return to Step 1.
- All tasks `[x]` → set `current_state: Closing`.

---

#### WriteTests

> **执行者：** code/task-runner sub-SKILL（由 Executing Task loop Step 1 dispatch）

**Entry:** Append `enter · WriteTests` to `tasks/t{X}/code-log.md`. Set `current_phase: WriteTests`.

**Actions:**

1. Write all test files for the current task. Do not create or modify any implementation files.
2. Use `code.test_command` from `workflow-config.json` for all test runs.

**Exit:** All test files written, no implementation changed → agent auto-advances to `VerifyRed`.

---

#### VerifyRed

> **执行者：** code/task-runner sub-SKILL（由 Executing Task loop Step 1 dispatch）

**Entry:** Append `enter · VerifyRed` to `code-log.md`. Set `current_phase: VerifyRed`.

**Actions:**

1. Run tests; append `test_run` entry to `code-log.md` with full output in fenced block.

**Exception:** If all tests pass unexpectedly → **STOP**. Report: tests have no constraining power over the implementation. Do not advance until resolved.

**Exit:** `test_run` log has at least one FAIL → agent auto-advances to `WriteImpl`.

---

#### WriteImpl

> **执行者：** code/task-runner sub-SKILL（由 Executing Task loop Step 1 dispatch）

**Entry:** Append `enter · WriteImpl` to `code-log.md`. Set `current_phase: WriteImpl`.

**Actions:**

1. Write minimal implementation to make failing tests pass. Do not modify any test files.

**Exit:** Implementation written, no test files modified → agent auto-advances to `VerifyGreen`.

---

#### VerifyGreen

> **执行者：** code/task-runner sub-SKILL（由 Executing Task loop Step 1 dispatch）

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
3. If `tdd_exempt` is set on this task (from task list or task frontmatter): advance directly to `Done`, skipping Refactor entirely (see P{tdd_exempt}).

**Exception:** Any FAIL → **STOP**. Report failures; do not advance until all tests pass.

**Exit:** All PASS + initial commit written → advance to `Refactor` (or `Done` if `tdd_exempt`).

---

#### Refactor

> **执行者：** code/task-runner sub-SKILL（由 Executing Task loop Step 1 dispatch）

**Entry:** Append `enter · Refactor` to `code-log.md`. Set `current_phase: Refactor`.

**Actions:**

1. Apply behavior-neutral code cleanup. Do not modify test files.
2. Re-run tests after each change; append `test_run` entry to `code-log.md`.
3. If any code changed: append `git_commit · amend` to `code-log.md`; execute `git commit --amend`; update `commit-ref.md` (`final_commit`, `amended: true`). Amend keeps task atomicity — Refactor is part of the same task, not a separate commit.
4. If no changes: skip step 3.

**Exception:** Test regression → **STOP**. Revert change before proceeding.

**Exit:** No behavior change + tests still PASS (or no changes made) → advance to `Done`.

---

#### Done

> **执行者：** code/task-runner sub-SKILL（由 Executing Task loop Step 1 dispatch）

**Entry:** Append `enter · Done` to `code-log.md`. Set `current_phase: Done`.

**Actions:**

1. Mark task `[x]` in `code-task-list.md`.
2. Verify all three Task Advance Gate conditions for this task:
   - ① `tasks/t{X}/commit-ref.md` exists
   - ② `tasks/t{X}/code-log.md` contains `enter · Done`
   - ③ `code-task-list.md` has this task marked `[x]`

   These are **preconditions for advancing**, not post-conditions. Do not proceed until all three are confirmed.

3. Output to conversation: `CHECKPOINT t{X}: commit SHA <sha>, commit-ref.md written, advancing to t{X+1}.` Do not advance until this line is output.

**Branch:**
- If another task remains → update `current_task` to t{X+1}, append `enter · WriteTests` to that task's `code-log.md`, set `current_phase: WriteTests`. Return to top of Task loop.
- If all tasks are `[x]` → set `current_state: Closing`. Do **not** set `Delivered` directly.

**Batch commit anti-pattern (prohibited):** Never commit changes for multiple tasks in a single `git commit`. Each task — including `tdd_exempt` tasks and documentation-only changes — must produce its own commit and its own `tasks/t{X}/commit-ref.md`.

---

## Closing

**Entry:** `current_state: Closing`. All tasks in `code-task-list.md` are `[x]`.

**Actions:**

1. Create `s{N}/closing-checklist.md` and complete each item:
   ```markdown
   - [ ] Full test suite re-run (PASS)
   - [ ] commit-ref count == task count
   - [ ] git status clean in worktree
   - [ ] All code-task-list items [x]
   ```
2. Run full test suite; append `test_run` to a session-level log or note in checklist.
3. Count `commit-ref.md` files; verify count matches task count.
4. Verify `git status` is clean in the worktree.
5. When all checklist items checked: wait for explicit user confirmation.
6. Write `human-delivery-gate.md` (`approved: true`).

**Exit:** `human-delivery-gate.md` written with `approved: true` → set `current_state: Delivered`.

---

## Delivered

**Condition:** `human-delivery-gate.md` exists with `approved: true`. `current_state: Delivered`.

AI must not self-declare session complete. Even if all tasks are `Done` and the closing checklist is fully checked, `Delivered` requires explicit human confirmation via the gate file.

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

## Supporting: work-order → code handoff

- Path B: `--task-list-ref` + `--task-refs`; `task.md` is self-contained.
- `tdd_exempt` from task list or task frontmatter: if set, `VerifyGreen` → `Done` directly (Refactor phase skipped entirely, not skipped from within Refactor).
