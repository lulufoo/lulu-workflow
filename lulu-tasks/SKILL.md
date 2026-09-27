---
name: lulu-tasks
description: >-
  Use when: 施工单, work-order, lulu-tasks, 任务拆分, task breakdown, TDD 准备, 施工单工作流,
  work-order workflow, 任务依赖图, task-list, 施工单评审, TWCA, WOQA,
  lulu-workflow lulu-tasks.
disable-model-invocation: true
---

# work-order-workflow

Decompose a Delivered tech-doc into independently executable TDD units (task files). Each task is self-contained with acceptance criteria, function specs, constraints, context, and dependencies for direct use in TDD sessions.

**Scope:** work-order workflow only. Input: Delivered tech-doc. Output: task file set.
<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-tasks` (before Session Foundation)
- Feature identification logic from `## Session Foundation`

Also read `../_subagent.md` (for `$SUBAGENT_TOOL` / `$SUBAGENT_AWAIT_*`).
</HARD-GATE>

**This workflow runs in Agent mode with path guard.**

## Commands


### `start` — Session-level, run before each work order

> Prerequisite: `init` has been run. The upstream tech-doc must be in `Delivered` state.

**Step 1: Identify active cycle** — `_runtime.md` § Session Foundation. Do not run start.py until `$CYCLE_ID` is confirmed.

**Step 2: Confirm tech-ref path**

**Feature container (`$CYCLE_TYPE == "feature"`):** Auto-parse `tech-ref` from the lulu-plan Delivered output in the current conversation (latest `tech-doc.md` path). Do **not** ask.

**Topic container:** Ask the user for the absolute path to the Delivered `tech-doc.md`. Do not auto-detect.

> "Please provide the absolute path to the Delivered tech-doc.md for this work order."

**Step 3: Run start**

```bash
python3 "$SKILL_DIR/scripts/tt_start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --tech-ref "<absolute-path-to-tech-doc.md>"
```
> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

---

## Session File Structure

```
$CACHE_DIR/<cycle_id>/lulu-tasks/
  session-state.md               ← active_doc: N (monotonically increasing)

  r{N}/                          ← Nth work order
    workflow-state.md            ← current_state, evaluate_round (AI writes; hook validates)
    task-list.md                 ← task index + Mermaid dependency graph + exclusions
    human-delivery-gate.md       ← delivery gate

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
| `Evaluating` | Probe-only eval of the work order |
| `Delivered` | Work-order finalized; handed off to lulu-code |

Note: `ReadyForDelivery` is deprecated as a hook-enforced state. It remains an AI-governed intermediate step within the Evaluating → Delivered transition (human-delivery-gate.md mechanism unchanged).

Allowed transitions:
- `Drafting → Evaluating`
- `Evaluating → Drafting`    ← `$TT_EVAL` disposition `drafting`
- `Evaluating → ReadyForDelivery` (internal, AI-governed; then human-delivery-gate → Delivered)

Hook enforces all transition pre-conditions. Denial messages are self-explanatory.

---

## Operating Rules

### Script Macros

| Macro | Command |
|-------|---------|
| `$TT_EVAL` | `python3 "$SKILL_DIR/scripts/tt_eval_control.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |

Subcommand contracts: module docstring / `--help`. Eval dispatch: `$SKILL_ROOT/eval/SKILL.md`.

### General

1. Do not read workflow-config files to load templates. Read files under `$SKILL_DIR/templates/` (Rule D1).
2. Read `session-state.md` → `active_doc: N` to determine current work-order round.
3. `r{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from document body or file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md`.
6. This workflow runs in Agent mode. Writes outside `$CACHE_DIR/`
   are blocked by the path guard hook while a session is active.

### Drafting Rules

**Rule D1 — Entry sequence**

On entering Drafting, read:
1. `workflow-state.md` → `tech_ref`, `evaluate_round`
2. Read work-order templates (stop if a file is missing):
   - `$SKILL_DIR/templates/31-work-order-tasklist-template.md`
   - `$SKILL_DIR/templates/30-work-order-task-template.md`
3. `tech-doc.md` (full content, from `tech_ref`)

Use those template files as format definitions.

**Rule D2 — Two-step generation (evaluate_round == 0, first entry)**

Step 1 — Generate `r{N}/task-list.md`:
1. Enumerate all change points from tech-doc
2. Group by Test-First logic (by test boundary, not by file)
3. Produce task list: task_id / title / target files / dependencies / tdd_exempt flag
4. Produce Mermaid dependency graph (acyclic)
5. Record exclusions (changes not included in this work order + reasons)
6. **Feature container:** Proceed to task.md generation without asking.
   **Topic container:** Wait for user to confirm the task breakdown before proceeding.

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
- `execution_worktree`：该 task 的执行位置（task 级，区别于 workspace.json 的 session 级 `worktree_path`）
  - target_repo 与主 worktree repo 相同 → 填 `"feature_worktree"`
  - target_repo 不同且需要 Preparing 阶段自动创建额外 worktree → 填 `"extra_repo_worktree"`，并通过 `target_repo` 查 `workspace.json.extra_worktrees[repo].path`
  - 需要指定项目根目录下的自定义相对路径 → 填 `"custom_path"`，并额外填写 `execution_worktree_path`
- `exit_contract`：固定值，所有 task 必填：
  ```yaml
  exit_contract:
    commit: required
    commit_ref_md: required
    code_log: required
  ```

After all task.md files are generated:
- **Feature container:** Write `workflow-state.md: Evaluating` immediately.
- **Topic container:** Ask: "All task.md files generated. Proceed to Evaluating?" Only write `workflow-state.md: Evaluating` after user confirms.

**Test-First constraint:** For each task, ask "What test proves this change is correct?" before "What function is needed?" Acceptance criteria always precede function specs.

**Rule D3 — Re-entry (evaluate_round > 0)**

When returning from Evaluating or ReadyForDelivery to Drafting:
1. Run `$TT_EVAL status`. Fix the work order from `last_issues`.
2. Edit the flagged task files directly. Skip the two-step generation flow.
3. After the fixes:
   - **Feature container:** Write `workflow-state.md: Evaluating` immediately.
   - **Topic container:** Ask: "All issues fixed. Re-enter Evaluating?" Only write `workflow-state.md: Evaluating` after user confirms.

**Rule D4 — TDD exemption**

Pure UI / structural changes with no logic branches may set `tdd_exempt: true` in the task frontmatter.

Effects:
- `Acceptance criteria` section becomes optional (fill `N/A` if no tests)
- `execution-admission` skips TDD order and test-case checks

**Rule D5 — Code reads during drafting**

Read code files on demand (only what's needed to understand existing types and function signatures). Never batch-load the codebase.

**Rule D6 — Output constraint**

`task-list.md` and `tasks/t{N}/task.md` are the **only AI-generated artifacts** in Drafting. Do not create other files.

### Evaluating Rules

**Rule E1 — Entry**

On entering Evaluating, write `workflow-state.md` with `current_state: Evaluating` and `evaluate_round` incremented by 1. Preserve `tech_ref`.

**Rule E2 — Probe loop**

Delivered tech-doc is the reference. Eval probes the work order and does not edit it.

1. Run `$TT_EVAL begin-pass`. A non-zero result is Blocking.
2. Pin `$EVAL_ADAPTER_CONFIG` = `$SKILL_DIR/eval/eval-profile.json`.
3. Load `$SKILL_ROOT/eval/SKILL.md` and execute its **Begin Eval** probe-only segment.
4. Pin the successful `complete-probe-only` JSON as `probe_result`.
5. Run `$TT_EVAL route-probe-result --probe-result-json '<probe_result JSON>'`.
   - `disposition: continue` → return to step 3. The next probe is `next_phase`.
   - `disposition: drafting` → write `workflow-state.md: current_state: Drafting`. Present `issues`. Fix them under Rule D3, then re-enter Evaluating.
   - `disposition: ready` → write `workflow-state.md: current_state: ReadyForDelivery`. Continue to Rule R1.
6. A non-zero `$TT_EVAL` result is Blocking: stop and report it.

Phases, in order: `structural-gate`, `compliance-crosscheck`, `execution-admission`. A finding stops the later phases.

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:
1. Display final `task-list.md` summary (task count, dependency graph, any exclusions)
2. **Feature container:** Auto-complete delivery — write `r{N}/human-delivery-gate.md`, write `r{N}/workflow-state.md` → `current_state: Delivered`, output the full list of `tasks/t{N}/task.md` paths, then immediately start `lulu-code` without waiting for user stage selection (this stage's inline handoff; overrides the generic wait-for-selection rule in `_transitions.md`).
3. **Topic container:** Wait for explicit delivery confirmation from user, then write `r{N}/human-delivery-gate.md`, write `r{N}/workflow-state.md` → `current_state: Delivered`, and output the full list of `tasks/t{N}/task.md` paths for the TDD session to consume.

<DELIVERY-GATE>
Before presenting next stages to the user, read `../_transitions.md` and follow the Stage Transitions rules.

**Exception — Feature container after Rule R1 step 2:** Do not present next stages; proceed directly to `lulu-code` per Rule R1.
</DELIVERY-GATE>

---

## Session File Formats

### r{N}/workflow-state.md

```markdown
---
version: 1
workflow: lulu-tasks
current_state: Drafting
evaluate_round: 0
tech_ref: /abs/path/$CACHE_DIR/<cycle_id>/lulu-plan/revision1/tech-doc.md
updated_at: 2026-05-17T09:00:00+08:00
---
```

> `tech_ref`: set by `start.py`; preserve on every manual write of `workflow-state.md`.

---

## work-order → TDD handoff

- `tech_ref`: **Feature container** — auto-parsed from lulu-plan Delivered output at `start`. **Topic container** — user-provided at `start`; never auto-detected. The two workflow directories are fully decoupled.
- `task.md` is self-contained: constraints and context sections explicitly copy from tech-doc so the TDD session only reads `task.md`.
- `tdd_exempt: true` tasks: TDD SKILL skips Red/Green/Refactor constraints.
- Execution order: follow the topological sort of the dependency graph in `task-list.md`.
