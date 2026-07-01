---
name: lulu-code
description: >-
  Use when: TDD, code session, 测试驱动开发, 写测试代码, 写实现代码, task-from-work-order, lulu-code workflow,
  lulu-dev-workflow lulu-code, git worktree delivery.
disable-model-invocation: true
---

# code-workflow

## Overview

Run TDD on work-order tasks in an isolated git worktree—one task per sub-agent dispatch, per-task commits, then a closing gate before delivery.

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason (stderr, exit code, or `TASK_FAILED`), and **wait** for user direction before continuing.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md`
</HARD-GATE>

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-code`

<HARD-GATE>
Do NOT proceed until you have read `../_subagent.md` 
</HARD-GATE>

## Commands

### `/lulu-code [<cycle_id>]` — Entry point

Derive `$CYCLE_ID` via `_runtime.md` § Session Foundation, or use the explicit `<cycle_id>` argument if provided.

<HARD-GATE>
`$CYCLE_ID` must be resolved before proceeding. If it cannot be resolved → stop and ask the user to provide it.
</HARD-GATE>

Run entry recovery probe, branch on stdout JSON:

```bash
python3 "$SKILL_DIR/scripts/tc_session_control.py" \
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

**Step 1: Run `start.py`**

```bash
python3 "$SKILL_DIR/scripts/tc_start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>"
```

> On non-zero exit: Apply § Blocking policy.

**Exit:** `start.py` succeeds → proceed to § Preparing.

---

## Preparing

### Entry

Run `prepare.py`; on non-zero exit, apply § Blocking policy.

```bash
python3 "$SKILL_DIR/scripts/tc_prepare.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)"
```

- `prepare.py` owns workspace setup, worktree preparation, and Preparing → Executing.
- Do not bypass `prepare.py` for workspace or worktree setup.

---

## Executing

### Entry 

Run `session_control.py`; follow `next_action`:
- `starting` → apply § Blocking policy
- `prepare` → ## Preparing
- `dispatch` → enter the task loop with `current_task` as `{task_id}`
- `closing` → proceed to § Closing
- `done` → report terminal state (session already Delivered)

```bash
python3 "$SKILL_DIR/scripts/tc_session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  get-pointer
```

### Task loop (1→N)

**Step 1: Dispatch sub-agent**

Invoke `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`. Prompt:

```
You are executing a single TDD task.
Load {actual $SKILL_ROOT}/lulu-code/task-runner/SKILL.md and follow its instructions.

## Input
{
  "task_id": "{task_id}",
  "cycle_dir": "{absolute $CACHE_DIR/$CYCLE_ID}",
  "project_root": "{absolute project root}"
}
```

**Step 2: Confirm task ready** (after sub-agent returns)

1. If sub-agent returned `TASK_FAILED` → apply § Blocking policy.

2. Run:

```bash
python3 "$SKILL_DIR/scripts/tc_session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  confirm-task-ready --task-id {task_id}
```

On non-zero exit → apply § Blocking policy.

3. On success, parse stdout JSON and **immediately output**:
   - `next_task_id` set → `CHECKPOINT t{X}: commit SHA <initial_commit>, task commit recorded, advancing to <next_task_id>.`
   - `next_task_id` null → `CHECKPOINT t{X}: commit SHA <initial_commit>, task commit recorded, advancing to Closing.`

4. Do not run advance-pointer until the CHECKPOINT line is output.

**Step 3: Advance pointer**

```bash
python3 "$SKILL_DIR/scripts/tc_session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  advance-pointer --completed-task t{X}
```

> On non-zero exit: Apply § Blocking policy.

Read stdout JSON:

- `next_action: dispatch` → enter Step 1 with `current_task` from advance-pointer JSON as `{task_id}`.
- `next_action: closing` → leave Task loop; proceed to § Closing → Delivered.

---

## Closing

Run:

```bash
python3 "$SKILL_DIR/scripts/tc_session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)" \
  deliver
```

> Precondition: `current_state` must be Closing (enforced by script).
> On non-zero exit: Apply § Blocking policy.

**Exit:** deliver succeeds → § Delivered.

---

## Delivered

Session complete; stop.

---
