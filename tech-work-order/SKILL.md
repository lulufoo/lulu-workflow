---
name: tech-work-order
description: >-
  Use when: 施工单, work-order, tech-work-order, 任务拆分, task breakdown, TDD 准备, 施工单工作流,
  work-order workflow, 任务依赖图, task-list, 施工单评审, TWCA, WOQA,
  lulu-dev-workflow tech-work-order.
disable-model-invocation: true
---

# work-order-workflow

Decompose a Delivered tech-doc into independently executable TDD units (task files). Each task is self-contained with acceptance criteria, function specs, constraints, context, and dependencies for direct use in TDD sessions.

**Scope:** work-order workflow only. Input: Delivered tech-doc. Output: task file set.
<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`

Also read `../_subagent.md` (for `$SUBAGENT_TOOL` / `$SUBAGENT_AWAIT_*`).
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/tech-work-order`

**This workflow runs in Agent mode with path guard.**

## Commands


### `start` — Session-level, run before each work order

> Prerequisite: `init` has been run. The upstream tech-doc must be in `Delivered` state.

**Step 1: Identify active cycle** — See `## Session Foundation` in `../_runtime.md`

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Step 2: Confirm tech-ref path**

Ask the user for the absolute path to the Delivered `tech-doc.md`. Do not auto-detect.

> "Please provide the absolute path to the Delivered tech-doc.md for this work order."

**Step 3: Run start**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --tech-ref "<absolute-path-to-tech-doc.md>"
```
> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

---

## Session File Structure

```
$CACHE_DIR/<cycle_id>/tech/work-order/
  session-state.md               ← active_doc: N (monotonically increasing)

  r{N}/                          ← Nth work order
    workflow-state.md            ← current_state, evaluate_round (AI writes; hook validates)
    task-list.md                 ← task index + Mermaid dependency graph + exclusions
    evaluate-state.md            ← evaluation sub-state (version: 2 schema)
    human-delivery-gate.md       ← delivery gate

    evaluate{M}/                 ← Mth evaluation round (monotonically increasing)
      wo-review-e{M}-tda.md      ← TDA: Tech-doc Admission report
      wo-review-e{M}-w0.md       ← W0: Structural Gate report
      wo-review-e{M}-w1.md       ← W1: TWCA Compliance Cross-check report
      wo-review-e{M}-w2.md       ← W2: WOQA Execution Admission report

    tasks/                       ← task file set
      t1/
        task.md                  ← TDD execution unit (self-contained)
      t2/
        task.md
```

---

## State Model

**Main state axis** (`workflow-state.md → current_state`) — hook-enforced:

| State | Description |
|-------|-------------|
| `Drafting` | Task file creation and modification |
| `Evaluating` | Evaluation phases running (eval-runner sub-agent) |
| `TDABlocked` | Evaluation suspended: SOT-DEFECT found in TDA or W1; awaiting human decision |
| `Delivered` | Work-order finalized; handed off to tech-code |

Note: `ReadyForDelivery` is deprecated as a hook-enforced state. It remains an AI-governed intermediate step within the Evaluating → Delivered transition (human-delivery-gate.md mechanism unchanged).

Allowed transitions:
- `Drafting → Evaluating`
- `Evaluating → TDABlocked`  ← eval-runner: current_dimension=FAILED, failure_type=sot_defect
- `Evaluating → Drafting`    ← eval-runner: current_dimension=FAILED, failure_type=structural
- `TDABlocked → Drafting`    ← human decides to abandon round (SOT fix externally)
- `Evaluating → ReadyForDelivery` (internal, AI-governed; then human-delivery-gate → Delivered)

Hook enforces all transition pre-conditions. Denial messages are self-explanatory.

---

## Operating Rules

### General

1. Read `$WORKFLOW_DIR/workflow-config.json` → `tech-work-order` section before driving the workflow.
2. Read `session-state.md` → `active_doc: N` to determine current work-order round.
3. `r{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from document body or file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md` and `evaluate-state.md`.
6. This workflow runs in Agent mode. Writes outside `$CACHE_DIR/`
   are blocked by the path guard hook while a session is active.

### Drafting Rules

**Rule D1 — Entry sequence**

On entering Drafting, read:
1. `workflow-state.md` → `tech_ref`, `evaluate_round`
2. Load work-order templates via `$FETCH_TEMPLATE` (see `../_runtime.md` → Template Fetch):
   - `Use $FETCH_TEMPLATE tech-work-order tasklist_template_url`
   - `Use $FETCH_TEMPLATE tech-work-order task_template_url`
3. `tech-doc.md` (full content, from `tech_ref`)

Read stdout from each invocation for format definitions. On failure, report error and stop current step.

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

**新增必填字段（sub-agent dispatch 所需）：**

- `target_repo`：target_files 所在 git repo 名称（不含路径）
  - 文件位于 worktree repo 内 → 填 worktree repo 名（如 `lulu-dev-skills`）
  - 文件位于 workflow 项目内 → 填 workflow 项目 repo 名（如 `lulu-workbench`）
- `task_worktree`：该 task 的操作目录（task 级，区别于 workspace.json 的 session 级 `worktree_path`）
  - target_repo 与主 worktree repo 相同 → 填 `"primary"`
  - target_repo 不同 → 填相对于项目根目录的 worktree 路径（Preparing 阶段自动创建）
- `exit_contract`：固定值，所有 task 必填：
  ```yaml
  exit_contract:
    commit: required
    commit_ref_md: required
    code_log: required
  ```

After all task.md files are generated, ask: "All task.md files generated. Proceed to Evaluating?"
Only write `workflow-state.md: Evaluating` after user confirms.

**Test-First constraint:** For each task, ask "What test proves this change is correct?" before "What function is needed?" Acceptance criteria always precede function specs.

**Rule D3 — Re-entry (evaluate_round > 0)**

When returning from Evaluating or ReadyForDelivery to Drafting:
1. Read `evaluate-state.md` → check `fix_severity` and issue summary from last round
2. Do **not** re-run the two-step flow; directly edit the flagged task files
3. If `post_split_scan_required: true`: before re-entering Evaluating, grep all task files for original task_id references and update them. Write `post_split_scan_done: true` in `evaluate-state.md` only after scan completes. A pending scan (`post_split_scan_done: false`) blocks the Drafting → Evaluating transition.
4. After fixes (and split scan if required), ask: "All issues fixed. Re-enter Evaluating?"

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
2. Note evaluation framework keys for eval-runner dispatch: `tda_url`, `twca_url`, `woqa_url` (section `tech-work-order`)
3. Initialize `evaluate-state.md` (version: 2 schema; `current_dimension: TDA`):

```yaml
---
version: 2
phase: evaluate
current_dimension: TDA

tda_status: pending
tda_sot_defect_count: 0

w0_status: pending
w0_total_issues: 0
w0_resolved_issues: 0

w1_status: pending
w1_total_issues: 0
w1_resolved_issues: 0
w1_sot_defect_count: 0
w1_wo_miss_count: 0

w2_status: pending
w2_total_issues: 0
w2_resolved_issues: 0
w2_sot_defect_count: 0
w2_wo_error_count: 0

post_split_scan_required: false
post_split_scan_done: false

failure_type: ""
fix_severity: ""
fix_severity_reason: ""
---
```

**Rule E2 — Delegate to eval-runner sub-agent**

Invoke eval-runner as a sub-agent. Pass the following prompt (fill in actual values):

```
You are executing a single work-order evaluation round.
Load {actual $SKILL_DIR}/eval-runner/SKILL.md and follow its instructions.

## Input
evaluate_round: {M}
session_dir: {abs_path_to r{N}/}
tech_doc_path: {abs_path_to tech-doc.md, from workflow-state.md tech_ref}
task_list_path: {abs_path_to task-list.md}
TEMPLATE_SECTION: tech-work-order
TEMPLATE_KEY_TDA:  tda_url
TEMPLATE_KEY_TWCA: twca_url
TEMPLATE_KEY_WOQA: woqa_url
PROJECT_ROOT: {project root absolute path}
execution_mode: {guided | autonomous}

## Current Evaluation State
{full content of evaluate-state.md}
```

The `## Current Evaluation State` section enables resume: eval-runner reads `current_dimension` and skips already-completed phases. If `evaluate-state.md` does not yet exist, eval-runner starts from TDA.

Await sub-agent completion (`$SUBAGENT_AWAIT_SYNC`). Read returned `exit_code` and proceed to Rule E3.

**Rule E3 — Exit verification**

After eval-runner returns, read `evaluate-state.md → current_dimension` as the authoritative exit signal:

| `current_dimension` | `failure_type` | Action |
|--------------------|---------------|--------|
| `DONE` | — | Write `workflow-state.md: current_state: ReadyForDelivery` (AI-governed; hook allows). Await human writing `human-delivery-gate.md`, then write `current_state: Delivered`. |
| `FAILED` | `sot_defect` | Write `workflow-state.md: current_state: TDABlocked`. Present the blocking report path to user. Inform: SOT defect found — resolve tech-doc, then start a new work-order round. |
| `FAILED` | `structural` | Write `workflow-state.md: current_state: Drafting`. Present the blocking report path to user. Fix structural issues, then re-enter Evaluating. |

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:
1. Display final `task-list.md` summary (task count, dependency graph, any exclusions)
2. Wait for explicit delivery confirmation from user
3. Write `r{N}/human-delivery-gate.md`
4. Write `r{N}/workflow-state.md` → `current_state: Delivered`
5. Output the full list of `tasks/t{N}/task.md` paths for the TDD session to consume

<DELIVERY-GATE>
Before presenting next stages to the user, read `../_transitions.md` and follow the Stage Transitions rules.
</DELIVERY-GATE>

---

## Session File Formats

### r{N}/workflow-state.md

```markdown
---
version: 1
workflow: tech-work-order
current_state: Drafting
evaluate_round: 0
tech_ref: /abs/path/$CACHE_DIR/<cycle_id>/tech/plan/revision1/tech-doc.md
updated_at: 2026-05-17T09:00:00+08:00
---
```

> `tech_ref`: set by `start.py`; preserve on every manual write of `workflow-state.md`.

### r{N}/evaluate-state.md

```yaml
---
version: 2
phase: evaluate
current_dimension: TDA        # active states: TDA | W0 | W1 | W2
                              # terminal states: DONE | FAILED
failure_type: ""              # sot_defect | structural | none (set when current_dimension: FAILED)

tda_status: pending           # pending | passed | failed
tda_sot_defect_count: 0

w0_status: pending            # pending | passed | failed
w0_total_issues: 0
w0_resolved_issues: 0

w1_status: pending            # pending | complete | blocked
w1_total_issues: 0
w1_resolved_issues: 0
w1_sot_defect_count: 0
w1_wo_miss_count: 0

w2_status: pending            # pending | complete
w2_total_issues: 0
w2_resolved_issues: 0
w2_sot_defect_count: 0
w2_wo_error_count: 0

post_split_scan_required: false
post_split_scan_done: false

fix_severity: ""              # critical | medium | minor | none
fix_severity_reason: ""
---
```

### evaluate{M}/wo-review-e{M}-{phase}.md

One report file per phase. All phases use the same issue row format:

```markdown
| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|-----------|------------|----------|---------|--------|----------|
```

| Column | Values |
|--------|--------|
| `root_cause` | `SOT-DEFECT` \| `WO-MISS` \| `WO-ERROR` \| `UNRESOLVABLE` |
| `sot_source` | tech-doc section or `—` if SOT not involved |
| `Severity` | `critical` \| `medium` \| `minor` |
| `Status` | `Fixed` \| `Escalated` \| `Noted` \| `Reclassified` |
| `Decision` | `fix` \| `escalate` \| `ignore` \| `reclassify→{root_cause}` |

---

## work-order → TDD handoff

- `tech_ref`: user-provided at `start`; never auto-detected; the two workflow directories are fully decoupled.
- `task.md` is self-contained: constraints and context sections explicitly copy from tech-doc so the TDD session only reads `task.md`.
- `tdd_exempt: true` tasks: TDD SKILL skips Red/Green/Refactor constraints.
- Execution order: follow the topological sort of the dependency graph in `task-list.md`.
## Execution Mode: Apply

Read `$EXECUTION_MODE` from Session Foundation (set by parent `../_runtime.md`). Default: `guided`.

| Mode | Behavior |
|------|---------|
| `guided` | Current behavior — all rules apply as documented |
| `autonomous` | Apply the overrides below; all other rules unchanged |

### Autonomous Overrides

| Rule | Autonomous Behavior |
|------|-----------------------|
| `start` Step 2 — tech-ref path | **Feature container (autonomous):** auto-parse `tech-ref` from the tech-plan Delivered output in the current conversation (latest `tech-doc.md` path). Do **not** ask. For topic containers or guided mode: unchanged (always ask). |
| Drafting D2 Step 1 — confirm task breakdown | Auto-confirm. Proceed to task.md generation without asking. |
| Drafting D2 Step 2 — "Proceed to Evaluating?" | Auto-confirm. Enter Evaluating without asking. |
| Drafting D3 re-entry — "All issues fixed. Re-enter Evaluating?" | Auto-confirm. |
| Evaluating E2 — eval-runner per-issue AskQuestion (WO issues) | Default: Fix. Apply fix without asking. SOT issues always require AskQuestion regardless of mode. |
| ReadyForDelivery R1 — delivery confirmation | **Feature container (autonomous):** auto-complete delivery — write `human-delivery-gate.md`, set `current_state: Delivered`; then auto handoff to `tech-code` (auto-chain). For topic containers or guided mode: unchanged (wait for explicit user confirmation). |
