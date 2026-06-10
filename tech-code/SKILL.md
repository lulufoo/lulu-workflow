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
**Output:** tests + implementation, per-task `commit-ref.md`, closing checklist, delivery approval  
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

**Actions:**

1. Run `prepare.py`; on non-zero exit report the error and halt.

```bash
python3 "$SKILL_DIR/scripts/prepare.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)"
```

Read stdout JSON for `slug`, `worktree_dir`, `branch`; use these values to execute **P1 → P2 → P3** from `git-workflow-standard.md`.

`prepare.py` writes `workspace.json`. Field definitions: see § Session files › Schema queries below.

> **P1 collision** (`wt/<branch>` already exists): worktree was created in a prior run — re-use it, skip P3.

2. After git worktree is ready, run:

```bash
python3 "$SKILL_DIR/scripts/prepare.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)" \
  --validate
```

> On non-zero exit: report the error and halt.

**Exit:** `--validate` succeeds → session is `Executing`; first task id is in stdout JSON (`current_task`).

---

## Executing

**Entry:** Run `get-pointer`; follow `next_action`:
- `dispatch` → enter the task loop with `current_task` as `{task_id}`
- `closing` → proceed to § Closing → Delivered
- `done` → report terminal state (session already Delivered)

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  get-pointer
```

### Task loop (1→N)

Resolve `$RESOLVED_MODEL` once before the loop — see `## Sub-agent Context › Config Resolution` in `../_subagent.md`, using `--stage tech-code`.

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

**Step 4: Advance pointer**

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  advance-pointer --completed-task t{X}
```

> On non-zero exit: halt and report.

Read stdout JSON:

- `next_action: dispatch` → enter Step 1 with `current_task` as `{task_id}`.
- `next_action: closing` → leave Task loop; proceed to § Closing → Delivered.

---

## Closing

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
5. Write `delivery-approval.md` (`approved: true`).
6. Run:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)" \
  deliver
```

> On non-zero exit: halt and report.

**Exit:** `deliver` succeeds → proceed to § Delivered.

---

## Delivered

Session complete; stop.

---

## Session files

**Session Round Index:** `$CACHE_DIR/<cycle_id>/tech/code/session-state.md` — defines `N`.

**Session Workspace:** `$CACHE_DIR/<cycle_id>/tech/code/s{N}/`

| Path (relative to prefix) | Purpose |
|---|---|
| `workflow-state.md` | Session state and current task (written by scripts only) |
| `workspace.json` | Worktree path, project root, branch |
| `code-task-list.md` | Task list from work-order |
| `closing-checklist.md` | Pre-delivery verification |
| `delivery-approval.md` | Delivery approval for Delivered |
| `tasks/t{X}/code-log.md` | Append-only task execution log |
| `tasks/t{X}/commit-ref.md` | Task commit SHA and message |

**Schema queries**

If you need a file's field definitions at runtime, run the corresponding action:

| File | Action |
|---|---|
| `session-state.md` | `python3 $SKILL_DIR/scripts/session_state_schema.py --schema` |
| `workflow-state.md` | `python3 $SKILL_DIR/scripts/workflow_state_schema.py --schema` |
| `workspace.json` | `python3 $SKILL_DIR/scripts/workspace_schema.py --schema` |

**Session control (orchestrator):** `python3 $SKILL_DIR/scripts/session_control.py` — `get-pointer`, `advance-pointer`, `deliver`. Do not write `workflow-state.md` directly.
