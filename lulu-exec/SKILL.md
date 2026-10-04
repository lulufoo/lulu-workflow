---
name: lulu-exec
description: >-
  Use when: execute a delivered work order, task exec, coding TDD, action task,
  lulu-exec workflow, lulu-workflow lulu-exec, git worktree delivery.
disable-model-invocation: true
---

# code-workflow

## Overview

Execute work-order tasks by `kind`. One task per sub-agent. `coding` runs in an isolated git worktree with TDD and a commit contract. `action` reaches a stated goal and records a receipt with evidence for every acceptance criterion; it runs in the project root unless the task names a worktree. Then a closing gate before delivery.

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason (stderr, exit code, or `TASK_FAILED`), and **wait** for user direction before continuing.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-exec` (before Session Foundation)
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../_subagent.md` 
</HARD-GATE>

## Commands

### `/lulu-exec [<cycle_id>]` — Entry point

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
  - **Feature container** (`$CYCLE_TYPE == feature`): Announce `current_state`, `active_session`, and `current_task` (Executing only); auto-resume into ## `{resume_section}` — do not ask Yes/No.
  - **Topic container** (`$CYCLE_TYPE == topic`): Show the same fields; ask to resume. **Yes** → ## `{resume_section}` · **No** → ## Starting.

> lulu-exec is on the feature stage line only (`transition-table.json`); topic exception documents fallback if `/lulu-exec` is invoked on a topic cycle.

---

## State machine

Session states: `Starting` → `Preparing` → `Executing` → `Closing` → `Delivered`

Task phases live in the runner for `$CTX.kind`. Do not run the TDD chain for `action`.

---

## Starting

**Step 1: Run `start.py`**

```bash
python3 "$SKILL_DIR/scripts/tc_start.py" \
  --cycle-id "<cycle_id>"
```

> On non-zero exit: Apply § Blocking policy.

**Exit:** `start.py` succeeds → proceed to § Preparing.

---

## Preparing

Load `references/preparing.md`.

---

## Executing

Load `references/executing.md`.

---

## Closing

**Feature container** (`$CYCLE_TYPE == feature`): Auto-complete delivery — run `deliver` without user confirmation.

**Topic container** (`$CYCLE_TYPE == topic`): Wait for explicit user confirmation before running `deliver`.

Run:

```bash
python3 "$SKILL_DIR/scripts/tc_session_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  deliver
```

> Precondition: `current_state` must be Closing (enforced by script).
> On non-zero exit: Apply § Blocking policy.

**Exit:** deliver succeeds → § Delivered.

---

## Delivered

Session complete; stop.

---
