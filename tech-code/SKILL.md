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

Run `session_control.py resolve-task-context` to build the dispatch input:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)" \
  resolve-task-context --task-id {task_id}
```

Invoke `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`, passing `$RESOLVED_MODEL` as `model` if set. Prompt:

```
You are executing a single TDD task.
Load {actual $SKILL_ROOT}/tech-code/task-runner/SKILL.md and follow its instructions.

## Input
{stdout of resolve-task-context command above}
```

**Step 2: Confirm task ready** (after sub-agent returns)

1. If sub-agent returned `TASK_FAILED` → stop, surface error and reason, wait for user.
2. Run:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  confirm-task-ready --task-id {task_id}
```

3. On non-zero exit → stop, report stderr, wait for user.
4. On success → parse stdout JSON; retain for Step 3 (`task_id`, `initial_commit`, `next_task_id`).

Validates exit contract: ① commit-ref + `initial_commit`, ② code-log `enter · Done`, ③ code-task-list `[x]`.

**Step 3: CHECKPOINT output**

Use Step 2 JSON `initial_commit` for the SHA (do not re-read files).
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

- `next_action: dispatch` → enter Step 1 with `current_task` from advance-pointer JSON as `{task_id}`.
- `next_action: closing` → leave Task loop; proceed to § Closing → Delivered.

---

## Closing

Run:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  --project-root "$(pwd)" \
  deliver
```

> Precondition: `current_state` must be Closing (enforced by script).
> On non-zero exit: halt and report.

**Exit:** deliver succeeds → § Delivered.

---

## Delivered

Session complete; stop.

---

