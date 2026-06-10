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

Run TDD on work-order tasks in an isolated git worktree—one task per sub-agent dispatch, per-task commits, then a closing gate before delivery.

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

## Commands

### `/tech-code [<cycle_id>]` — Entry point

Derive `$CYCLE_ID` from active context (see `_runtime.md § Session Foundation`), or use the explicit `<cycle_id>` argument if provided.

<HARD-GATE>
`$CYCLE_ID` must be resolved before proceeding. If it cannot be resolved → stop and ask the user to provide it.
</HARD-GATE>

Run entry recovery probe, branch on stdout JSON:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  check-recovery
```

- `recoverable: false` → ## Starting
- `recoverable: true`:

<HARD-GATE>
Show `current_state`, `active_session`, and `current_task` (Executing only); ask to resume.

- **Yes** → ## `{resume_section}`
- **No** → ## Starting
</HARD-GATE>

---

## State machine

Session states: `Starting` → `Preparing` → `Executing` → `Closing` → `Delivered`

Task phases (under Executing): `WriteTests` → `VerifyRed` → `WriteImpl` → `VerifyGreen` → `Refactor` → `Done`

---

## Starting

**Step 1: Load `docs/git/git-workflow-standard.md`** — required before any git operations.

**Step 2: Run `start.py`**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>"
```

> On non-zero exit: report the blocking stage to the user. Do not retry.

**Exit:** `start.py` succeeds → `workflow-state.md` `current_state` is already `Preparing` → proceed to § Preparing.

---

## Preparing

### Entry

Run `prepare.py`; on non-zero exit report the error and halt.

```bash
python3 "$SKILL_DIR/scripts/prepare.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)"
```

- `prepare.py` owns workspace setup, worktree preparation, and Preparing → Executing.
- Do not create `workspace.json` or worktrees manually.

---

## Executing

### Entry 

Run `session_control.py`; follow `next_action`:
- `starting` → halt and report
- `prepare` → ## Preparing
- `dispatch` → enter the task loop with `current_task` as `{task_id}`
- `closing` → proceed to § Closing
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

### Entry

Run `session_control.py`; follow `next_action`:

- `closing` → continue Actions below
- anything else → halt and report

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  get-pointer
```

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
5. Run:

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
| `tasks/t{X}/code-log.md` | Append-only task execution log |
| `tasks/t{X}/commit-ref.md` | Task commit SHA and message |

**Schema queries** — `python3 $SKILL_DIR/scripts/<script>.py`

If you need a file's field definitions at runtime, run the corresponding action:

| File | Action |
|---|---|
| `session-state.md` | `session_state_schema.py --schema` |
| `workflow-state.md` | `workflow_state_schema.py --schema` |
| `workspace.json` | `workspace_schema.py --schema` |
| `session_control.py` | `session_control.py` — `check-recovery`, `get-pointer`, `advance-pointer`, `deliver` |
