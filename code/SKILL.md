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
cat <project-root>/$CACHE_DIR/<work-order-feature-id>/work-order/*/workflow-state.md
```
- `current_state` is not `Delivered` → error: "work-order `<id>` not yet delivered (current state: `<state>`). Cannot start code workflow." Stop.
- Path does not exist → error: "work-order `<id>` not found. Please verify the ID." Stop.

Path A:
- Read `<tech-doc-path>` to confirm file exists
- Not found → error: "tech-doc not found: `<path>`." Stop.

**Step 4: Collect upstream file paths**

Path B:
```bash
<project-root>/$CACHE_DIR/<work-order-feature-id>/work-order/<revision>/task-list.md
<project-root>/$CACHE_DIR/<work-order-feature-id>/work-order/<revision>/tasks/*/task.md
```

Path A: use `<tech-doc-path>` directly.

**Step 5: Run start.py**

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

```
$CACHE_DIR/<feature_id>/code/
  session-state.md              ← active_session: N (monotonically increasing)

  s{N}/                         ← Nth code session
    workflow-state.md           ← current_state / current_task / current_phase (AI writes; authoritative pointer)
    code-task-list.md           ← checkbox progress list (execution anchor)
    human-delivery-gate.md      ← written after all tasks Done and user confirms

    tasks/
      t{X}/
        code-log.md             ← sole per-task execution log (append-only event stream)
```

**Deprecated (do not create in new sessions):** `red-run.md`, `green-run.md`. Red/Green evidence lives in `code-log.md` as `test_run` events.

**Template:** On task entry, create `code-log.md` from `$SKILL_DIR/templates/code-log.template.md` (replace `t{X}` with the task id).

---

## State Model

### Session level

States: `Executing → Completed`

| From | To | Trigger |
|------|----|---------|
| `[*]` | `Executing` | start command |
| `Executing` | `Completed` | All tasks in code-task-list.md are `[x]` |

### Task Phase level

```
WriteTests → VerifyRed → WriteImpl → VerifyGreen → Refactor → Done
                                              ↑
                             tdd_exempt: true may skip directly to Done
```

| From Phase | To Phase | Pre-condition |
|-----------|---------|---------------|
| `[*]` | `WriteTests` | all depends_on tasks are `[x]` |
| `WriteTests` | `VerifyRed` | — |
| `VerifyRed` | `WriteImpl` | `code-log.md` contains `test_run · VerifyRed` with full output + `failure_reason` |
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
7. **code-log.md is append-only:** add new events at the end only; never rewrite prior entries or use `## Phase N` report sections.
8. **Event title format:** `### <ISO-8601>Z · <type> · <label>` where `type` is one of `phase_enter`, `phase_exit`, `test_run`, `note`, `task_done`.
9. **Do not create** `red-run.md` or `green-run.md` in new sessions.

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

**On task entry**

1. Create `tasks/t{X}/code-log.md` from `$SKILL_DIR/templates/code-log.template.md` (replace `t{X}`).
2. Append `phase_enter · WriteTests` (and `phase_exit` when leaving a phase, before the next `phase_enter`).

**Phase 1 — WriteTests**

- Input: task.md "acceptance criteria" (Path B) or task description from code-task-list.md (Path A)
- Output: write test file (`test_file` path)
- Constraint: **do not write any implementation code**
- Done when: all acceptance criteria have corresponding test cases
- `tdd_exempt: true`: append `note` documenting skipped phases; proceed to WriteImpl or Done per task scope
- Exit: append `phase_exit · WriteTests` (optional), then `workflow-state.md: current_phase: VerifyRed`

**Phase 2 — VerifyRed (mandatory for non-exempt tasks)**

- Action: run `test_command` (Shell), capture full output
- Expected: all tests FAIL; failure reason = function/class does not exist (not a syntax error)
- Exceptions:
  - Tests pass → tests cover existing behavior; return to Phase 1 to fix tests
  - Syntax error → fix syntax, re-run, repeat until failure reason is correct
- Record: append `test_run · VerifyRed` to `code-log.md` with `command`, `failure_reason`, and full output in a fenced block
- **Do not** create `red-run.md`
- Exit: write `workflow-state.md: current_phase: WriteImpl`

**Phase 3 — WriteImpl**

- Output: write implementation file (`target_file` path) or doc/template per task
- Constraints:
  - **Do not modify tests** (absolute prohibition; N/A for tdd_exempt doc-only tasks)
  - Minimum implementation only
  - Comply with all hard rules in task.md "constraints" section
- Exit: write `workflow-state.md: current_phase: VerifyGreen`

**Phase 4 — VerifyGreen**

- Action: run `test_command` (Shell), capture full output — or for `tdd_exempt`, append `test_run · VerifyGreen` with an acceptance checklist table instead of shell output
- Expected: all tests PASS, no warnings or errors (non-exempt)
- Failure: fix implementation (never the tests), re-run, repeat until all PASS
- Record: append `test_run · VerifyGreen` with `result: ALL PASS` and full output (or checklist)
- **Do not** create `green-run.md`
- Exit: write `workflow-state.md: current_phase: Refactor` (or `Done` if tdd_exempt)

**Phase 5 — Refactor**

- Action: deduplicate, rename, extract helpers, eliminate magic numbers
- Constraint: re-run tests after each refactor change; append `test_run · Refactor` for each run
- Prohibition: do not add new behavior or new tests
- `tdd_exempt: true` tasks skip this phase
- Exit: write `workflow-state.md: current_phase: Done`

**Task completion actions (after each task Done)**

1. Append `task_done` to `code-log.md`
2. Update `code-task-list.md`: `[ ]` → `[x]`, status → `✅ Done`, increment frontmatter `done` count
3. If tasks remain: write `workflow-state.md: current_task: t{X+1}, current_phase: WriteTests`
4. If all tasks done: write `workflow-state.md: current_state: Completed`

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
task_list_ref: /abs/path/$CACHE_DIR/<feature_id>/code/s1/code-task-list.md
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
task_list_ref: /abs/path/$CACHE_DIR/<feature_id>/work-order/r1/task-list.md
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

Append-only event log. See `$SKILL_DIR/templates/code-log.template.md`.

```markdown
# Code Log — t1

> Append-only: add entries at the end only.

### 2026-05-27T10:00:12Z · phase_enter · WriteTests
...

### 2026-05-27T10:06:30Z · test_run · VerifyRed
command: `npm test`
failure_reason: validateEmail is not a function
```
<full output>
```

**Prohibited in new sessions:** `## Progress`, `## Audit summary`, phase report tables replacing the event log, new `red-run.md` / `green-run.md`.

---

## Implementation note (hooks)

- Unified `scripts/hook_guard.py` `_STAGES` lists `diagnostic`, `work-order`, `tech`, `product` only — **`code` is intentionally omitted** so agents can write repository source files without cache hook friction.
- `code/scripts/hook_guard.py` contains state-machine logic but is **not dispatched** by the unified entry point; its path matcher expects `.../code/<conv_id>/s{N}/` while the real layout is `.../<feature_id>/code/s{N}/` → no enforcement in production.
- Other stage hooks guard `.md` writes under `CACHE_DIR` only; they do **not** implement workflow-state transition state machines (verify against source, not legacy SKILL claims).
- **Do not** document code-stage transitions as "hook enforced" unless `code` is deliberately re-enabled with a corrected design.

---

## work-order → code handoff

- **Path B input**: `--task-list-ref` (Delivered work-order task-list.md) + `--task-refs` (all task.md files)
- **task.md is self-contained**: constraints and context sections explicitly copy from tech-doc; code session only reads task.md
- **tdd_exempt**: read from task.md frontmatter or `[tdd_exempt]` in code-task-list.md; skips Phase 1/2/5
- **Test command**: read from `workflow-config.json → code.test_command`; confirm before each test run
## Execution Mode

Read `$EXECUTION_MODE` from Feature Context (set by parent `SKILL.md`). Default: `assisted`.

| Mode | Behavior |
|------|---------|
| `assisted` | Current behavior — all rules apply as documented |
| `self-service` | Apply the overrides below; all other rules unchanged |

### Self-Service Overrides

| Rule | Self-Service Behavior |
|------|-----------------------|
| startup Step 6 — confirm start execution | Auto-confirm. Start first task without asking. |
| Path A — draft code-task-list confirmation | Auto-confirm. Write `code-task-list.md` immediately without asking. |
| Session completion — C3 delivery confirmation | **Unchanged: always wait for explicit user confirmation.** |
