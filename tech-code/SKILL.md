---
name: tech-code
description: >-
  Use when: TDD, code session, 测试驱动开发, 写测试代码, 写实现代码, Red Green Refactor,
  code-task-list, task-from-work-order, tech-code workflow,
  lulu-dev-workflow tech-code, git worktree delivery.
disable-model-invocation: true
---

# code-workflow

Execute Test-Driven Development from a Delivered work-order task set, with git worktree delivery and per-task commits. **Scope:** TDD code generation in a dedicated worktree. Input: Delivered work-order task set. Output: tests + implementation, per-task `commit-ref.md`, closing checklist, human delivery gate. Session lifecycle: **Preparing → Executing → Closing → Delivered**.

**This workflow runs in Agent mode.** (requires writing code files and executing Shell commands)

**`/tech-code` authorizes** automatic `git commit` / `git commit --amend` inside the session worktree during Executing. Push, PR, CI, and review are post-code (out of scope).

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`

Also read `../_subagent.md` and load:
- Sub-agent model convention (`$RESOLVED_MODEL`) from `## Sub-agent Context › Config Resolution`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/tech-code`

## Commands

### `/tech-code <input>` — Entry point

| Format | Meaning | Example |
|--------|---------|---------|
| *(no input)* | Derive feature from active context (`$CYCLE_ID` resolved in Step 1) | `/tech-code` |
| `<cycle_id>` | Explicit feature override; format: `<timestamp>-<uuid>` | `/tech-code 20260601141338-3764ab2b` |

If the user's input does not match this format, stop and output the usage error.

---

### AI startup sequence (after valid input)

**Step 0: Load `docs/git/git-workflow-standard.md`** — required before any git operations.

**Step 1: Identify active cycle** — See `## Session Foundation` in `../_runtime.md`

**Step 2–4:** Parse input, validate upstream Delivered state, collect paths.

**Step 5: Run `start.py`** — bootstraps `current_state: Preparing` with empty `current_task` / `current_phase`.
> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

**Step 6:** Read `code-task-list.md`; display tasks; wait for confirmation before execution.

---

## Session files

```
$CACHE_DIR/<cycle_id>/tech/code/
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

**Step 0: Task-spec schema validation (pre-execution gate)**

For each task.md delivered by the work-order, validate the schema:
- Verify frontmatter contains `target_repo` (non-empty string)
- Verify frontmatter contains `task_worktree` (`"primary"` or a valid relative path)
- Verify frontmatter contains `exit_contract` with keys `commit`, `commit_ref_md`, `code_log` all set to `required`
- Any missing field: output the missing field name and task_id, halt, wait for user correction
- Verify `task_worktree` consistency: all tasks sharing a target_repo must use the same task_worktree value (mismatch: schema conflict error)

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
   Omit `extra_worktrees` entirely if all tasks target the primary repo.

**Exit:** All worktree and branch setup complete, `workspace.json` written → update `workflow-state.md`: `current_state: Executing`, set `current_task` to first runnable task, `current_phase: WriteTests`. All subsequent TDD edits and commits run inside the worktree directory.

---

## Executing

**Entry:** `current_state: Executing`, `current_task` = first runnable task, `current_phase: WriteTests`.

On session resume: read `workflow-state.md`; resume from `current_task` / `current_phase`.

Process tasks 1→N in sequence. Advance `current_phase` only when `current_state` is `Executing`.

### Task loop (1→N)

**Invariant (one commit per task):** Never commit changes for multiple tasks in a single `git commit`. Each task must produce its own commit and its own `tasks/t{X}/commit-ref.md`.

**Invariant (no direct execution):** Task phases run in sub-agent only; orchestrator must not execute phases directly.

Resolve `$RESOLVED_MODEL` once before the loop — see `## Sub-agent Context › Config Resolution` in `../_subagent.md`, using `--stage tech-code`.

For each task in order:

Phase lifecycle is fully defined in `task-runner/SKILL.md`. The orchestrator dispatches per-task and validates the exit contract; it does not define or duplicate phase logic.

**Step 1: Dispatch sub-agent**

Read `task.md` → resolve `task_worktree` to `worktree_abs_path`:
- `"primary"` → absolute path of workspace.json `worktree_path`
- relative path → `{project_root}/{task_worktree}` (absolute)

Invoke `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`, passing `$RESOLVED_MODEL` as `model` if set. Prompt:

```
You are executing a single TDD task.
Load {actual $SKILL_ROOT}/code/task-runner/SKILL.md and follow its instructions.
(substitute the real $SKILL_ROOT path above before dispatching)

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

Read `tasks/t{X}/commit-ref.md → initial_commit` for the SHA.
Output: `CHECKPOINT t{X}: commit SHA <sha>, commit-ref.md written, advancing to t{X+1}.`
Do not advance until this line is output.

**Step 4: Branch**

- More tasks remain → update `current_task` to t{X+1}; return to Step 1.
- All tasks `[x]` → set `current_state: Closing`.

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

## § Autonomous Overrides

Read `$EXECUTION_MODE` from Session Foundation (set by parent `../_runtime.md`). Default: `guided`.

The overrides below apply only when `$EXECUTION_MODE == "autonomous"` **and** `cycle_type == "feature"`. All other rules unchanged.

**Auto-chain entry point:** In autonomous + feature mode, this stage may be entered automatically after `tech-work-order` delivers (see `§ Autonomous Tech Line Auto-Chain` in `../_transitions.md`). No user `/code` command is required; the orchestrator auto-invokes the startup sequence.

| Rule | Autonomous Behavior |
|------|-----------------------|
| AI startup Step 6 — task confirmation | Auto-skip. Proceed directly to Executing without waiting for user confirmation. |
| Closing step 5 — delivery gate confirmation | Auto-complete. Write `human-delivery-gate.md` (`approved: true`) without waiting for explicit user confirmation. |

---

## Supporting: tech-work-order → tech-code handoff

- Path B: `--task-list-ref` + `--task-refs`; `task.md` is self-contained.
- `tdd_exempt` from task list or task frontmatter: if set, `VerifyGreen` → `Done` directly (execution handled by `task-runner/SKILL.md`).
