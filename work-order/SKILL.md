---
name: work-order
description: >-
  Use when: 施工单, work-order, 任务拆分, task breakdown, TDD 准备, 施工单工作流,
  work-order workflow, 任务依赖图, task-list, 施工单评审, TWCA, WOQA,
  lulu-dev-workflow work-order.
disable-model-invocation: true
---

# work-order-workflow

Decompose a Delivered tech-doc into independently executable TDD units (task files). Each task is self-contained with acceptance criteria, function specs, constraints, context, and dependencies for direct use in TDD sessions.

**Scope:** work-order workflow only. Input: Delivered tech-doc. Output: task file set.
**Platform context** — detect once at session start, substitute `$SKILL_DIR`, `$WORKFLOW_DIR`, and `$PLATFORM` throughout:

| | Cursor | Copilot |
|---|---|---|
| `$SKILL_DIR` | `~/.cursor/skills/lulu-dev-workflow/work-order` | `~/.copilot/skills/lulu-dev-workflow/work-order` |
| `$WORKFLOW_DIR` | `.cursor/lulu-dev-workflow` | `.github/lulu-dev-workflow` |
| `$PLATFORM` | `cursor` | `copilot` |

> **Detect:** `COPILOT_AGENT=1` env var → Copilot; `VSCODE_TARGET_SESSION_LOG` template variable present → Copilot; otherwise → Cursor.

**This workflow runs in Agent mode with path guard.**

---

## Commands


### `start` — Session-level, run before each work order

> Prerequisite: `init` has been run. The upstream tech-doc must be in `Delivered` state.

**Step 1: Identify active feature**

**Fast path:** Find the latest `LULU-DEV-WORKFLOW: <id>` line in this conversation's AI responses (skip conversation-summary blocks). If found and no ambiguity signal → use it, proceed to next step.

**Slow path:** Read `$CACHE_DIR/features.json` → display list + "New" option → wait for confirmation. If New → run `feature_init.py` for a new `feature_id`.

Append `LULU-DEV-WORKFLOW: <feature_id>` to every workflow AI response.

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Step 2: Confirm tech-ref path**

Ask the user for the absolute path to the Delivered `tech-doc.md`. Do not auto-detect.

> "Please provide the absolute path to the Delivered tech-doc.md for this work order."

**Step 3: Run start**

> `start.py` runs archive first: restores the current conv from `_archive/` if needed, then moves other **Delivered** convs to `_archive/<conv_id>/work-order/`. Non-terminal convs stay in the hot zone.

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --feature-id "<feature_id>" \
  --tech-ref "<absolute-path-to-tech-doc.md>"
```

---

## Session File Structure

```
.cache/$PLATFORM/lulu-dev-workflow/<feature_id>/work-order/
  session-state.md               ← active_doc: N (monotonically increasing)

  r{N}/                          ← Nth work order
    workflow-state.md            ← current_state, evaluate_round (AI writes; hook validates)
    task-list.md                 ← task index + Mermaid dependency graph + exclusions
    evaluate-state.md            ← W1/W2 evaluation progress
    human-delivery-gate.md       ← delivery gate

    evaluate{M}/                 ← Mth evaluation round (monotonically increasing)
      wo-review-e{M}1.md         ← W1: TWCA cross-check report
      wo-review-e{M}2.md         ← W2: WOQA quality review report

    tasks/                       ← task file set
      t1/
        task.md                  ← TDD execution unit (self-contained)
      t2/
        task.md
```

**Cold zone** (Delivered convs archived on next `/work-order` start):

```
.cache/$PLATFORM/lulu-dev-workflow/_archive/<conv_id>/work-order/
  session-state.md
  r1/ … r{N}/
```

- Only the **active** `r{N}/workflow-state.md` with `current_state: Delivered` triggers archive (whole conv).
- The current conversation conv is never archived; cold-only convs are restored before the next round.

Historical work orders: `.cache/$PLATFORM/lulu-dev-workflow/_archive/<conv_id>/work-order/r{N}/`

---

## State Model

States: `Drafting` → `Evaluating` → `ReadyForDelivery` → `Delivered`

Allowed transitions:
- `Drafting → Evaluating`
- `Evaluating → ReadyForDelivery`  ← requires evaluate pre-conditions (hook enforced)
- `Evaluating → Drafting`
- `ReadyForDelivery → Drafting`
- `ReadyForDelivery → Delivered`  ← requires `human-delivery-gate.md` (hook enforced)

Hook enforces all transition pre-conditions. Denial messages are self-explanatory.

---

## Operating Rules

### General

1. Read `$WORKFLOW_DIR/workflow-config.json` → `work_order` section before driving the workflow.
2. Read `session-state.md` → `active_doc: N` to determine current work-order round.
3. `r{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from document body or file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md` and `evaluate-state.md`.
6. This workflow runs in Agent mode. Writes outside `.cache/$PLATFORM/lulu-dev-workflow/`
   are blocked by the path guard hook while a session is active.

### Drafting Rules

**Rule D1 — Entry sequence**

On entering Drafting, read:
1. `workflow-state.md` → `tech_ref`, `evaluate_round`
2. `workflow-config.json` → `work_order.task_template_url`, `work_order.tasklist_template_url`
3. `tech-doc.md` (full content, from `tech_ref`)

Fetch the templates via `gh api` (same pattern as install), read their format definitions.

**Rule D2 — Two-step generation (evaluate_round == 0, first entry)**

Step 1 — Generate `r{N}/task-list.md`:
1. Enumerate all change points from tech-doc
2. Group by Test-First logic (by test boundary, not by file)
3. Produce task list: task_id / title / target files / dependencies / tdd_exempt flag
4. Produce Mermaid dependency graph (acyclic)
5. Record exclusions (changes not included in this work order + reasons)
6. Wait for user to confirm the task breakdown before proceeding

Step 2 — Generate `tasks/t{N}/task.md` one by one:
1. Write acceptance criteria first (test case descriptions: normal / boundary / edge cases)
2. Derive function specs from acceptance criteria
3. Copy constraints verbatim from tech-doc (hard rules)
4. Copy context from tech-doc (soft background)
5. Fill in dependencies (dependent task_ids)

After all task.md files are generated, ask: "All task.md files generated. Proceed to Evaluating?"
Only write `workflow-state.md: Evaluating` after user confirms.

**Test-First constraint:** For each task, ask "What test proves this change is correct?" before "What function is needed?" Acceptance criteria always precede function specs.

**Rule D3 — Re-entry (evaluate_round > 0)**

When returning from Evaluating or ReadyForDelivery to Drafting:
1. Read `evaluate-state.md` → check `fix_severity` and issue summary from last round
2. Do **not** re-run the two-step flow; directly edit the flagged task files
3. After fixes, ask: "All issues fixed. Re-enter Evaluating?"

**Rule D4 — TDD exemption**

Pure UI / structural changes with no logic branches may set `tdd_exempt: true` in the task frontmatter.

Effects:
- `Acceptance criteria` section becomes optional (fill `N/A` if no tests)
- W2 evaluation skips Dimension 2 (TDD compliance) and Dimension 5 (test case quality)

**Rule D5 — Code reads during drafting**

Read code files on demand (only what's needed to understand existing types and function signatures). Never batch-load the codebase.

**Rule D6 — Output constraint**

`task-list.md` and `tasks/t{N}/task.md` are the **only AI-generated artifacts** in Drafting. Do not create other files.

### Evaluating Rules

**Rule E1 — Entry sequence**

On entering Evaluating:
1. Increment `evaluate_round` in `workflow-state.md` (write `current_state: Evaluating, evaluate_round: M`)
2. Read `workflow-config.json` → `work_order.twca_url`, `work_order.woqa_url`
3. Initialize `evaluate-state.md`:

```
version: 1
phase: evaluate
current_dimension: w1
w1_status: pending
w1_total_issues: 0
w1_resolved_issues: 0
w2_status: pending
w2_total_issues: 0
w2_resolved_issues: 0
total_issues: 0
resolved_issues: 0
fix_severity: ""
fix_severity_reason: ""
```

**Rule E2 — W1 → W2 sequence**

Always execute W1 first, then W2. Do not skip or reorder.

| Dim | seq | Report file | Inputs |
|-----|-----|-------------|--------|
| W1 (TWCA) | 1 | `evaluate{M}/wo-review-e{M}1.md` | `task-list.md` + all `task.md` files + `tech-doc.md` + `twca_url` framework |
| W2 (WOQA) | 2 | `evaluate{M}/wo-review-e{M}2.md` | all `task.md` files + `woqa_url` framework |

**Rule E3 — W1 (TWCA) execution**

W1 checks three directions:

1. **Coverage:** every tech-doc change point has a corresponding task (exclusion list is the exemption registry)
2. **Traceability:** each task's acceptance criteria traces back to a specific tech-doc requirement
3. **Consistency:** task constraints match tech-doc hard rules, no contradictions

For each direction:
1. Load inputs, read `twca_url` framework
2. Write `evaluate{M}/wo-review-e{M}1.md` skeleton (issues list per direction)
3. Per issue: present to user via AskQuestion → user decides → fix task file → update review file immediately

Never batch-fix. One issue, one fix, one file update.

**Rule E4 — W2 (WOQA) execution**

W2 checks 6 dimensions:

| # | Dimension | Check | tdd_exempt skips |
|---|-----------|-------|-----------------|
| 1 | Granularity | Each task covers 1–3 function changes, completable in one TDD session | no |
| 2 | TDD compliance | Acceptance criteria precede function specs; Test-First order maintained | yes |
| 3 | Spec completeness | Function signatures complete; no empty acceptance criteria; no TBD | no |
| 4 | Constraint coverage | All hard rules explicitly copied from tech-doc | no |
| 5 | Test case quality | Normal / boundary / edge scenarios all covered | yes |
| 6 | Dependency graph | No cycles; execution order is sound | no |

Same per-issue flow as W1: present via AskQuestion → user decides → fix → update file immediately.

**Rule E5 — Completion**

After W2 complete:
1. Assess overall `fix_severity` (critical / medium / minor) and write `fix_severity_reason`
2. Write `evaluate-state.md` with `current_dimension: done`, all statuses `complete`
3. Write `workflow-state.md` → `current_state: ReadyForDelivery` (hook will validate)

**Rule E6 — Issue presentation**

Present each issue via AskQuestion, one at a time:
- Option A: Confirm, fix the issue
- Option B: Ignore, no impact on delivery

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:
1. Display final `task-list.md` summary (task count, dependency graph, any exclusions)
2. Wait for explicit delivery confirmation from user
3. Write `r{N}/human-delivery-gate.md`
4. Write `r{N}/workflow-state.md` → `current_state: Delivered`
5. Output the full list of `tasks/t{N}/task.md` paths for the TDD session to consume

---

## Session File Formats

### r{N}/workflow-state.md

```markdown
---
version: 1
workflow: work-order
current_state: Drafting
evaluate_round: 0
tech_ref: /abs/path/.cache/$PLATFORM/lulu-dev-workflow/<feature_id>/tech/revision1/tech-doc.md
updated_at: 2026-05-17T09:00:00+08:00
---
```

> `tech_ref`: set by `start.py`; preserve on every manual write of `workflow-state.md`.

### r{N}/evaluate-state.md

```markdown
---
version: 1
phase: evaluate
current_dimension: w1

w1_status: pending
w1_total_issues: 0
w1_resolved_issues: 0

w2_status: pending
w2_total_issues: 0
w2_resolved_issues: 0

total_issues: 0
resolved_issues: 0

fix_severity: ""
fix_severity_reason: ""
---
```

### evaluate{M}/wo-review-e{M}N.md

W1 and W2 share the same base structure; W1 groups issues by direction (Coverage / Traceability / Consistency), W2 groups by dimension number.

```markdown
# {W1 TWCA Cross-Check|W2 WOQA Quality Review} — r{N} round {M}

**Date:** YYYY-MM-DD
**Refs:** [W1: tech_ref + twca_url / W2: woqa_url]

## {Direction 1: Coverage | Dimension 1: Granularity | ...}

| # | Issue | task_id | Severity | Status | Decision |
|---|-------|---------|----------|--------|---------|
| {W1|W2}-1 | ... | t2 | critical/medium/minor | ✅ Fixed | fix |
```

---

## work-order → TDD handoff

- `tech_ref`: user-provided at `start`; never auto-detected; the two workflow directories are fully decoupled.
- `task.md` is self-contained: constraints and context sections explicitly copy from tech-doc so the TDD session only reads `task.md`.
- `tdd_exempt: true` tasks: TDD SKILL skips Red/Green/Refactor constraints.
- Execution order: follow the topological sort of the dependency graph in `task-list.md`.