---
name: code
description: >-
  Use when: TDD, tdd session, 测试驱动开发, 写测试代码, 写实现代码, Red Green Refactor,
  tdd-task-list, task-from-work-order, task-from-tech, tdd workflow,
  lulu-dev-workflow tdd.
disable-model-invocation: true
---

# code-workflow

Execute Test-Driven Development from a Delivered tech-doc or work-order task set: write tests first, confirm Red, write minimal implementation, confirm Green, then refactor.

**Scope:** TDD code generation. Input: Delivered tech-doc (Path A) or Delivered work-order task set (Path B). Output: test files + implementation files.
<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Feature Context`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/code`

**This workflow runs in Agent mode.** (requires writing code files and executing Shell commands)

---

## Commands


### `/code <input>` — Entry point

| Format | Meaning | Example |
|--------|---------|---------|
| `work-order/<uuid>` | Source: specified work-order session | `/code work-order/1d2ea64b-065d-4e12-9008-9163d475ee00` |
| `tech <path-to-tech-doc.md>` | Source: specified tech doc | `/code tech /abs/path/tech-doc.md` |

If the user's input does not match either format, stop and output:

```
Invalid input. Usage:

  From work-order:  /code work-order/<work-order-conv-id>
  From tech doc:    /code tech <path-to-tech-doc.md>

Prerequisite: upstream must be in Delivered state.
```

---

### AI startup sequence (after valid input)

**Step 1: Identify active feature** — See `## Feature Context` in `../SKILL.md`

**Step 2: Parse `<input>` type**

- Starts with `work-order/` → **Path B**, extract `<work-order-feature-id>`
- Starts with `tech ` → **Path A**, extract `<tech-doc-path>`
- Other → invalid; output error above and stop

**Step 3: Validate upstream state**

Path B:
```bash
cat <project-root>/.cache/$PLATFORM/lulu-dev-workflow/<work-order-feature-id>/work-order/*/workflow-state.md
```
- `current_state` is not `Delivered` → error: "work-order `<id>` not yet delivered (current state: `<state>`). Cannot start code workflow." Stop.
- Path does not exist → error: "work-order `<id>` not found. Please verify the ID." Stop.

Path A:
- Read `<tech-doc-path>` to confirm file exists
- Not found → error: "tech-doc not found: `<path>`." Stop.

**Step 4: Collect upstream file paths**

Path B:
```bash
<project-root>/.cache/$PLATFORM/lulu-dev-workflow/<work-order-feature-id>/work-order/<revision>/task-list.md
<project-root>/.cache/$PLATFORM/lulu-dev-workflow/<work-order-feature-id>/work-order/<revision>/tasks/*/task.md
```

Path A: use `<tech-doc-path>` directly.

**Step 5: Run start.py**

> `start.py` runs archive first: restores the current conv from `_archive/` if needed, then moves other **Completed** convs to `_archive/<conv_id>/code/`. **Executing** convs stay in the hot zone.

Path B:
```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --feature-id "<feature_id>" \
  --mode task-from-work-order \
  --task-list-ref "<abs-path-to-task-list.md>" \
  --task-refs <abs-path-to-t1/task.md> <abs-path-to-t2/task.md> ...
```

Path A:
```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --feature-id "<feature_id>" \
  --mode task-from-tech \
  --tech-ref "<abs-path-to-tech-doc.md>"
```

> `<feature_id>` is the active feature ID from `LULU-DEV-WORKFLOW:` (identified in Step 1).

**Step 6: Read `code-task-list.md`, display task list, wait for user confirmation before starting execution**

---

## Session File Structure

**Hot zone** (active / in-progress convs):

```
.cache/$PLATFORM/lulu-dev-workflow/<feature_id>/code/
  session-state.md              ← active_session: N (monotonically increasing)

  s{N}/                         ← Nth code session
    workflow-state.md           ← current_state / current_task / current_phase (AI writes; hook validates)
    code-task-list.md           ← checkbox progress list (execution anchor)
    human-delivery-gate.md      ← written after all tasks Done and user confirms

    tasks/
      t{X}/
        code-log.md             ← timestamps + notes per phase
        red-run.md              ← Phase 2: test run output (hook depends on this file)
        green-run.md            ← Phase 4: test run output
```

**Cold zone** (Completed convs archived on next `/code` start):

```
.cache/$PLATFORM/lulu-dev-workflow/_archive/<conv_id>/code/
  session-state.md              ← same layout as hot zone
  s1/ … s{N}/
```

Archive rules (handled by `archive.py` via `start.py`):

- Only convs whose **active** `s{N}/workflow-state.md` has `current_state: Completed` are moved to cold storage (whole conv, all sessions). Conv IDs may be UUIDs or slugs (e.g. `p4-tauri-migration`).
- Convs with `current_state: Executing` remain in the hot zone (safe for multi-window).
- The current conversation conv is never archived; if it exists only in cold storage, `start.py` restores it before creating the next session round.

To read historical sessions: `.cache/$PLATFORM/lulu-dev-workflow/_archive/<conv_id>/code/s{N}/`

---

## State Model

### Session level

States: `Executing → Completed`

| From | To | Trigger |
|------|----|---------|
| `[*]` | `Executing` | start command |
| `Executing` | `Completed` | Hook: all tasks in code-task-list.md are `[x]` |

### Task Phase level

```
WriteTests → VerifyRed → WriteImpl → VerifyGreen → Refactor → Done
                                              ↑
                             tdd_exempt: true may skip directly to Done
```

| From Phase | To Phase | Pre-condition (hook enforced) |
|-----------|---------|-------------------------------|
| `[*]` | `WriteTests` | all depends_on tasks are `[x]` |
| `WriteTests` | `VerifyRed` | — |
| `VerifyRed` | `WriteImpl` | `tasks/t{X}/red-run.md` exists |
| `WriteImpl` | `VerifyGreen` | — |
| `VerifyGreen` | `Refactor` | — |
| `VerifyGreen` | `Done` | tdd_exempt: true |
| `Refactor` | `Done` | — |
| `Done` | `WriteTests` | next task |

---

## Operating Rules

### General

1. Read `$WORKFLOW_DIR/workflow-config.json` → `code.test_command` for the test runner; use this command in Phase 2 / 4 / 5.
2. Read `session-state.md` → `active_session: N` to determine current session round.
3. `s{N}/workflow-state.md` is the authoritative state — write it to request a transition.
4. Never infer state from file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md`.
6. Preserve all fields when writing `workflow-state.md`: `mode`, `task_list_ref`, `current_task`, `current_phase`.

### Startup sequence

> Follows Step 5 above, after `start.py` completes successfully.

**Path B (task-from-work-order):**
1. `start.py` auto-generates `code-task-list.md` (all tasks ⏳ Pending)
2. Read `code-task-list.md`, display task list with dependencies to user
3. Wait for user confirmation → begin first task

**Path A (task-from-tech):**
1. Read `<tech-doc-path>`, analyze change points using Test-First logic, draft `code-task-list.md` (task_id from t1, granularity: single function change)
2. Display draft to user, wait for confirmation
3. After confirmation, write `s{N}/code-task-list.md`
4. Write `workflow-state.md`: `current_task: t1, current_phase: WriteTests`
5. Begin first task

### Phase execution rules (one loop per task)

**Phase 1 — WriteTests**

- Input: task.md "acceptance criteria" (Path B) or task description from code-task-list.md (Path A)
- Output: write test file (`test_file` path)
- Constraint: **do not write any implementation code**
- Done when: all acceptance criteria have corresponding test cases
- Exit: write `workflow-state.md: current_phase: VerifyRed`

**Phase 2 — VerifyRed (mandatory, cannot skip)**

- Action: run `test_command` (Shell), capture full output
- Expected: all tests FAIL; failure reason = function/class does not exist (not a syntax error)
- Exceptions:
  - Tests pass → tests cover existing behavior; return to Phase 1 to fix tests
  - Syntax error → fix syntax, re-run, repeat until failure reason is correct
- Record: write `tasks/t{X}/red-run.md` (full output + one-line confirmation: "Failure reason: function does not exist")
- Exit: write `workflow-state.md: current_phase: WriteImpl` (hook validates red-run.md exists)

**Phase 3 — WriteImpl**

- Output: write implementation file (`target_file` path)
- Constraints:
  - **Do not modify tests** (absolute prohibition)
  - Minimum implementation only
  - Comply with all hard rules in task.md "constraints" section
- Exit: write `workflow-state.md: current_phase: VerifyGreen`

**Phase 4 — VerifyGreen**

- Action: run `test_command` (Shell), capture full output
- Expected: all tests PASS, no warnings or errors
- Failure: fix implementation (never the tests), re-run, repeat until all PASS
- Record: write `tasks/t{X}/green-run.md` (full output)
- Exit: write `workflow-state.md: current_phase: Refactor` (or `Done` if tdd_exempt)

**Phase 5 — Refactor**

- Action: deduplicate, rename, extract helpers, eliminate magic numbers
- Constraint: re-run tests after each refactor change to confirm all still PASS
- Prohibition: do not add new behavior or new tests
- tdd_exempt: true tasks skip this phase
- Exit: write `workflow-state.md: current_phase: Done`

**Task completion actions (after each task Done)**

1. Update `code-task-list.md`: `[ ]` → `[x]`, status → `✅ Done`, increment frontmatter `done` count
2. Write `tasks/t{X}/code-log.md` (timestamps + notes per phase)
3. If tasks remain: write `workflow-state.md: current_task: t{X+1}, current_phase: WriteTests`
4. If all tasks done: write `workflow-state.md: current_state: Completed` (hook validates)

**Session completion actions**

1. Display final `code-task-list.md` (all tasks ✅ Done)
2. Wait for explicit user confirmation
3. Write `s{N}/human-delivery-gate.md` (`approved: true`)
4. Write `s{N}/workflow-state.md: current_state: Completed`

---

## Session File Formats

### s{N}/workflow-state.md

```markdown
---
version: 1
workflow: code
current_state: Executing
mode: task-from-work-order
task_list_ref: /abs/path/.cache/$PLATFORM/lulu-dev-workflow/<feature_id>/code/s1/code-task-list.md
current_task: t2
current_phase: WriteImpl
updated_at: 2026-05-17T09:00:00+08:00
---
```

> Preserve all fields on every write: `mode`, `task_list_ref`, `current_task`, `current_phase`.

### s{N}/code-task-list.md

```markdown
---
source: work-order
task_list_ref: /abs/path/.cache/$PLATFORM/lulu-dev-workflow/<feature_id>/work-order/r1/task-list.md
total: 5
done: 1
---

# Code Task List

- [x] t1 · validateEmail · `src/utils/validators.ts` · ✅ Done
- [ ] t2 · validatePhone · `src/utils/validators.ts` · 🔴 WriteImpl
- [ ] t3 · authService integration · `src/services/auth.ts` · ⏳ Pending (depends: t1, t2)
- [ ] t4 · integration tests · `tests/auth.test.ts` · ⏳ Pending (depends: t3)
- [ ] t5 · error handling layer · `src/utils/error.ts` · ⏳ Pending
```

`tdd_exempt` tasks are marked with `[tdd_exempt]` at the end of the line:
```markdown
- [ ] t6 · update button styles · `src/components/Button.tsx` · ⏳ Pending [tdd_exempt]
```

### s{N}/tasks/t{X}/code-log.md

```markdown
# t{X} TDD Log

| Phase | Time | Output / Notes |
|-------|------|----------------|
| WriteTests | 2026-05-17T10:00Z | `tests/utils/validators.test.ts` — 3 cases |
| VerifyRed | 2026-05-17T10:02Z | 3 FAIL — validateEmail is not a function |
| WriteImpl | 2026-05-17T10:05Z | `src/utils/validators.ts` — validateEmail, 15 lines |
| VerifyGreen | 2026-05-17T10:06Z | 3 PASS |
| Refactor | 2026-05-17T10:08Z | extracted EMAIL_REGEX constant — 3 PASS |
```

---

## work-order → code handoff

- **Path B input**: `--task-list-ref` (Delivered work-order task-list.md) + `--task-refs` (all task.md files)
- **task.md is self-contained**: constraints and context sections explicitly copy from tech-doc; code session only reads task.md
- **tdd_exempt**: read from task.md frontmatter or `[tdd_exempt]` in code-task-list.md; skips Phase 1/2/5
- **Test command**: read from `workflow-config.json → code.test_command`; confirm before each test run