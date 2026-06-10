---
name: tech-code
description: >-
  Use when: TDD, code session, 测试驱动开发, 写测试代码, 写实现代码, Red Green Refactor,
  code-task-list, task-from-work-order, tech-code workflow,
  lulu-dev-workflow tech-code, git worktree delivery.
disable-model-invocation: true
---

# code-workflow

## Overview

**Input:** Delivered work-order task set  
**Output:** tests + implementation, per-task `commit-ref.md`, closing checklist, human delivery gate  
**Scope:** TDD code generation in a dedicated worktree, with git worktree delivery and per-task commits  
**Session lifecycle:** `Preparing → Executing → Closing → Delivered`

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md`
</HARD-GATE>

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/tech-code`

<HARD-GATE>
Do NOT proceed until you have read `../_subagent.md` 
</HARD-GATE>

- Sub-agent model convention (`$RESOLVED_MODEL`) from `## Sub-agent Context › Config Resolution`

- `/tech-code` authorizes** automatic `git commit` / `git commit --amend` inside the session worktree during Executing.

## Commands

### `/tech-code [<cycle_id>]` — Entry point

Derive `$CYCLE_ID` from active context (see `_runtime.md § Session Foundation`), or use the explicit `<cycle_id>` argument if provided.

<HARD-GATE>
`$CYCLE_ID` must be resolved before proceeding. If it cannot be resolved → stop and ask the user to provide it.
</HARD-GATE>

### AI startup sequence

**Step 1: Load `docs/git/git-workflow-standard.md`** — required before any git operations.

**Step 2: Run `start.py`**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>"
```

> On non-zero exit: report the blocking stage to the user. Do not retry.

**Step 3:** Read `code-task-list.md`; display tasks; wait for confirmation before execution.

---

## State machine

**SSOT:** `$SKILL_DIR/transition-whitelist.json` — parallel `session` and `task` machines with `states` enums and `allowed_transitions`. This SKILL documents semantics only; do not duplicate transition tables here.

`transition-whitelist.json` defines which transitions are *allowed*; each state section below defines *when* to trigger — the two are complementary and non-overlapping.

Session states: `Preparing` → `Executing` → `Closing` → `Delivered`

Task phases (under Executing): `WriteTests` → `VerifyRed` → `WriteImpl` → `VerifyGreen` → `Refactor` → `Done`

---

## Preparing

**Actions:** Run `prepare.py`; on non-zero exit report the error and halt. 

```bash
python3 "$SKILL_DIR/scripts/prepare.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)"
```

Read stdout JSON for `slug`, `worktree_dir`, `branch`; use these values to execute **P1 → P2 → P3** from `git-workflow-standard.md`.

Separately, `prepare.py` writes `workspace.json`.
Field definitions: see § Session files › Schema queries below.

> **P1 collision** (`wt/<branch>` already exists): worktree was created in a prior run — re-use it, skip P3.

**Exit:** `workspace.json` written → `workflow-state.md`: `current_state: Executing`, `current_task` = first task, `current_phase: WriteTests`.

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

Run `scripts/resolve_task_context.py` to build the dispatch input:

```bash
python3 "$SKILL_DIR/scripts/resolve_task_context.py" \
  --task-id {task_id} \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)"
```

Invoke `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`, passing `$RESOLVED_MODEL` as `model` if set. Prompt:

```
You are executing a single TDD task.
Load {actual $SKILL_ROOT}/tech-code/task-runner/SKILL.md and follow its instructions.

## Input
{stdout of resolve_task_context.py}
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
5. Checklist complete → write `human-delivery-gate.md` (`approved: true`) → set `current_state: Delivered`.

**Exit:** `human-delivery-gate.md` written with `approved: true` → set `current_state: Delivered`.

---

## Delivered

**Condition:** All closing checklist items pass. `human-delivery-gate.md` exists with `approved: true`. `current_state: Delivered`.

---

## Session files

**Session Round Index:** `$CACHE_DIR/<cycle_id>/tech/code/session-state.md` — defines `N`.

**Session Workspace:** `$CACHE_DIR/<cycle_id>/tech/code/s{N}/`

| Path (relative to prefix) | Purpose |
|---|---|
| `workflow-state.md` | Session state and current task/phase |
| `workspace.json` | Worktree path, project root, branch |
| `code-task-list.md` | Task list from work-order |
| `closing-checklist.md` | Pre-delivery verification |
| `human-delivery-gate.md` | Human sign-off for Delivered |
| `tasks/t{X}/code-log.md` | Append-only task execution log |
| `tasks/t{X}/commit-ref.md` | Task commit SHA and message |

**Schema queries**

If you need a file's field definitions at runtime, run the corresponding action:

| File | Action |
|---|---|
| `session-state.md` | `python3 $SKILL_DIR/scripts/session_state_schema.py --schema` |
| `workflow-state.md` | `python3 $SKILL_DIR/scripts/workflow_state_schema.py --schema` |
| `workspace.json` | `python3 $SKILL_DIR/scripts/workspace_schema.py --schema` |
