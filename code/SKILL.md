---
name: code
description: >-
  Use when: TDD, code session, 测试驱动开发, 写测试代码, 写实现代码, Red Green Refactor,
  code-task-list, task-from-work-order, task-from-tech, code workflow,
  lulu-dev-workflow code, git worktree delivery.
disable-model-invocation: true
---

# code-workflow

Execute Test-Driven Development from a Delivered tech-doc or work-order task set, with git worktree delivery and per-task commits. Session lifecycle: **Preparing → Executing → Closing → Delivered**.

**Scope:** TDD code generation in a dedicated worktree. 
- Input: Delivered work-order task set (Path B).
- Output: tests + implementation, per-task `commit-ref.md`, closing checklist, human delivery gate.

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Feature Context`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/code`

**This workflow runs in Agent mode.** (requires writing code files and executing Shell commands)

**`/code` authorizes** automatic `git commit` / `git commit --amend` inside the session worktree during L2.3. Push, PR, CI, and review are **post-code** (out of scope).

---

## Commands

### `/code <input>` — Entry point

| Format | Meaning | Example |
|--------|---------|---------|
| `work-order/<uuid>` | Source: specified work-order session | `/code work-order/1d2ea64b-065d-4e12-9008-9163d475ee00` |

If the user's input does not match either format, stop and output the usage error from the prior spec.

---

### AI startup sequence (after valid input)

**Step 0: Load `docs/git/git-workflow-standard.md`** — required before any git operations in L1.

**Step 1: Identify active feature** — See `## Feature Context` in `../SKILL.md`

**Step 2–4:** Parse input, validate upstream Delivered state, collect paths (unchanged from prior flow).

**Step 5: Run `start.py`** (does **not** run git; bootstraps `current_state: Preparing` with empty `current_task` / `current_phase`).

**Step 6:** Read `code-task-list.md`; display tasks; wait for confirmation before L1/L2 execution.

---

## Session file structure

```
$CACHE_DIR/<feature_id>/code/
  session-state.md
  s{N}/
    workflow-state.md           ← session + task pointer (authoritative)
    workspace.json              ← L1: worktree_path, branch, created_at
    code-task-list.md
    closing-checklist.md        ← L3 (Closing)
    human-delivery-gate.md      ← required before Delivered

    tasks/t{X}/
      code-log.md               ← append-only action log (task-level only)
      commit-ref.md             ← L2.3: initial/final SHA, message, amended
```

Do **not** create `red-run.md` or `green-run.md` for new sessions. Red/Green evidence belongs in `code-log.md` as `test_run` entries.

Optional seed: `$SKILL_DIR/templates/code-log.template.md` (replace `t{X}`).

---

## State model

**SSOT:** `$SKILL_DIR/transition-whitelist.json` — parallel `session` and `task` machines with `states` enums and `allowed_transitions`. This SKILL documents semantics and conventions only; **do not duplicate** transition tables here.

### Session states

`Preparing` → `Executing` → `Closing` → `Delivered`

| Phase | Meaning |
|-------|---------|
| **Preparing** | L1: create worktree + branch (see below); write `s{N}/workspace.json`. Agent runs git; `start.py` does not. |
| **Executing** | Task TDD loop (1→N) while session stays Executing. |
| **Closing** | L3: complete `closing-checklist.md` (retest, commit-ref count, clean worktree, all tasks `[x]`). |
| **Delivered** | After `human-delivery-gate.md` (`approved: true`). |

**Session completion (correct order):** when all tasks in `code-task-list.md` are `[x]`, set `current_state: Closing` — **not** `Delivered`. After checklist + user gate, set `Delivered`.

### Task phases (under Executing)

`WriteTests` → `VerifyRed` → `WriteImpl` → `VerifyGreen` → `Refactor` → `Done` (with `tdd_exempt` shortcut VerifyGreen → `Done` per whitelist `when`).

| Phase | Exit criterion | Trigger | On unexpected result |
|-------|---------------|---------|----------------------|
| `WriteTests` | All test files written; no implementation changed | Agent auto-advances | — |
| `VerifyRed` | `test_run` log has at least one FAIL | Agent auto-advances | Unexpected all-PASS → STOP, report tests not covering implementation |
| `WriteImpl` | Implementation written; no test files modified | Agent auto-advances | — |
| `VerifyGreen` | `test_run` log all PASS | Agent auto-advances; `tdd_exempt` skips Refactor → Done | Any FAIL → STOP, report failures |
| `Refactor` | No behavior change + tests still PASS, or skip | Agent auto-advances (skippable) | Test regression → STOP |
| `Done` | `commit-ref.md` written | Session-level logic takes over | — |

---

## Conventions

1. Advance `current_phase` only when `current_state` is `Executing`.
2. After task `Done`: if another task remains → update `current_task`, append `enter · WriteTests` in that task's `code-log.md`, set phase `WriteTests`; if all tasks `[x]` → session transition `Executing` → `Closing`.
3. `code-log.md` is **task-level** only; session artifacts (`workspace.json`, `closing-checklist.md`, gate) are separate files.
4. `/code` authorizes auto commit/amend in the worktree during L2.3; do not push/open PR from this stage.
5. All task-phase transitions are **agent-driven** — no user confirmation required, except when `VerifyGreen` unexpectedly FAILs.
6. Writing `enter · <phase>` to `code-log.md` is the materialized record of a phase advance; the phase is considered entered once written.
7. `transition-whitelist.json` defines which transitions are *allowed*; the exit criterion table above defines *when* to trigger — the two are complementary and non-overlapping.
8. **Task advance gate:** Before setting `current_task: t{N+1}`, verify all three exist for t{N}: `tasks/t{N}/commit-ref.md`, `tasks/t{N}/code-log.md` containing `enter · Done`, and `[x]` in `code-task-list.md`. These are preconditions, not post-conditions.
9. **Observable checkpoint:** After each task `Done`, output to conversation before advancing: `CHECKPOINT t{N}: commit SHA {sha}, commit-ref.md written, advancing to t{N+1}.` Do not advance until this line is output.

---

## L1 — Preparing (worktree)

1. Read `$WORKFLOW_DIR/workflow-config.json` → `code.git` (`worktree_base`, `branch_pattern`, `default_type`, `commit_message_template`).
2. Derive `<slug>` from feature id or scope; build paths from config:
   - worktree dir: `{worktree_base}/<slug>/` (default `.cache/worktrees/<slug>/`)
   - branch: apply `branch_pattern` with `{type}` = `default_type` (default `wt/feat-<slug>`)
3. Execute **P1 → P2 → P3** from `git-workflow-standard.md` using the derived `<slug>` and `code.git` config values.
4. Write `s{N}/workspace.json`:

```json
{
  "worktree_path": ".cache/worktrees/<slug>/",
  "branch": "wt/feat-<slug>",
  "created_at": "2026-05-27T10:00:00Z"
}
```

5. Update `workflow-state.md`: `current_state: Executing`, then set `current_task` and `current_phase: WriteTests` for the first runnable task.

All subsequent TDD edits and L2.3 commits run **inside** the worktree directory.

---

## L2 — Executing (TDD loop)

Entry: `current_state: Executing`, `current_task` = first runnable task, `current_phase: WriteTests`.

Process tasks 1→N in sequence. Per-phase behavior: see **Operating rules**. Git at task boundaries: see **L2.3**.

---

## L2.3 — Git commits at task boundaries

After **VerifyGreen** (implementation green): `git_commit · initial` in `code-log.md`; record `tasks/t{X}/commit-ref.md`:

```markdown
task_id: t2
branch: wt/feat-code-git-delivery
initial_commit: a1b2c3d
final_commit: a1b2c3d
commit_message: "feat(code): t2 validatePhone"
amended: false
recorded_at: 2026-05-27T14:00:00Z
```

After **Refactor** if code changed: `git_commit · amend`; update `commit-ref.md` (`final_commit`, `amended: true`).

Use `code.git.commit_message_template` for messages. End each task with `enter · Done` (+ optional summary in body).

**Batch commit anti-pattern (prohibited):** Never commit changes for multiple tasks in a single `git commit`. Each task — including `tdd_exempt` tasks and documentation-only changes — must produce its own commit and its own `tasks/t{X}/commit-ref.md`. Per-task atomicity is not waived by any task property.

---

## L3 — Closing

While `current_state: Closing`, create/update `s{N}/closing-checklist.md`:

```markdown
- [ ] Full test suite re-run (PASS)
- [ ] commit-ref count == task count
- [ ] git status clean in worktree
- [ ] All code-task-list items [x]
```

When all items checked, wait for explicit user confirmation, write `human-delivery-gate.md` (`approved: true`), then `current_state: Delivered`.

---

## code-log action model

**Format:** `### <ISO8601> · <action>[ · <target>]` + optional body. **Append-only.**

| action | target | meaning |
|--------|--------|---------|
| `enter` | phase name | phase transition |
| `test_run` | — | run `code.test_command`; full output in fenced block |
| `git_commit` | `initial` \| `amend` | L2.3 commit; SHA and message in body |

No `red-run` / `green-run` action types or standalone red/green files for new sessions.

---

## Operating rules (summary)

1. `code.test_command` from `workflow-config.json` for all `test_run` entries.
2. `workflow-state.md` is authoritative; use full `Write` for updates; preserve `mode`, `task_list_ref`, `current_task`, `current_phase`.
3. **WriteTests:** tests only, no implementation.
4. **VerifyRed / VerifyGreen:** run tests; log via `test_run`; fix tests vs impl per TDD rules.
5. **WriteImpl:** minimal implementation; do not modify tests.
6. **Refactor:** behavior-neutral; re-run tests after each change; skip when `tdd_exempt`.
7. On each task Done: update `code-task-list.md`; if last task → `Closing`, else next task + `WriteTests`.

---

## work-order → code handoff

- Path B: `--task-list-ref` + `--task-refs`; `task.md` is self-contained.
- `tdd_exempt` from task list / task frontmatter.
- Config: `code.test_command`, `code.git` (see `init.py`).

## Execution Mode

Read `$EXECUTION_MODE` from Feature Context. Default: `assisted`.

| Mode | Behavior |
|------|----------|
| `assisted` | Confirmations as documented |
| `self-service` | Auto-confirm task list start; **delivery gate before Delivered still requires explicit user confirmation** |
