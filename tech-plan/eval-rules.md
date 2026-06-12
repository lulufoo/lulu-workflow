---
rule-guard:
  globs:
    - "**/*.md"
---

# Evaluating Orchestration Rules

Loaded by `tech-plan/SKILL.md` on entering `Evaluating` state.
Follow this document exactly. Do not execute any evaluation step before reading it.

---

## Phase 1 — Initialize (E1)

Prerequisite: `$SESSION_CONTROL start-evaluating` succeeded (writes `workflow-state.md` and initializes `evaluate-state.md`).

1. Read `workflow-state.md` → confirm `current_state: Evaluating`, `evaluate_round: M`
2. Read `evaluate-state.md` → confirm `phase: evaluate` and dimension fields match `mode`
3. Proceed to Phase 2

---

## Phase 2 — Build dispatch list (E2)

| `mode` | Dispatch sequence |
|--------|------------------|
| `product` | `[e1, e2, e3]` |
| `tech` | `[e2, e3]` |

---

## Phase 3 — Per-dimension loop

For each `dim` in dispatch list:

1. Write `evaluate-state.md`: `current_dimension: {dim}`, `{dim}_status: in_progress`

2. Dispatch `eval-runner` (`$SUBAGENT_TOOL`, `$SUBAGENT_AWAIT_SYNC`). Prompt:

```text
Load {$SKILL_ROOT}/tech-plan/eval-runner/SKILL.md and follow its instructions.

## Input
DIMENSION:            {dim}
TECH_DOC_PATH:        {absolute path to revision{N}/tech-doc.md}
EVALUATE_STATE_PATH:  {absolute path to revision{N}/evaluate-state.md}
EVALUATE_DIR:         {absolute path to revision{N}/evaluate{M}/}
EXECUTION_MODE:       {guided | autonomous}
[e1 only] PRODUCT_REF: {product_ref from workflow-state.md}
[e1 only] TEMPLATE_SECTION: tech-plan
[e1 only] TEMPLATE_KEY:     ptc_url
[e3 only] TEMPLATE_SECTION: tech-plan
[e3 only] TEMPLATE_KEY:     tpef_url (feature cycle) | shaping_tpef_url (topic cycle)
PROJECT_ROOT:         {project root absolute path}
```

3. Await completion

4. Read `evaluate-state.md` → check `current_dimension`:
   - if `abandoned` → jump to **E6 Abandon Handler**, STOP
   - else → verify `{dim}_status: complete`; continue to next dimension

---

## Phase 4 — Completion (E4)

After all dimensions complete:

1. Read all completed review files (`evaluate{M}/tech-review-e{M}1.md`, `e{M}2.md`, `e{M}3.md`) — only those that exist
2. Collect the `Severity` column of every issue row; determine `fix_severity` as the highest level found (critical > medium > minor); if all ignored, use `minor`
3. Write `fix_severity_reason` (one sentence citing the most severe issue)
4. Write `evaluate-state.md`: `current_dimension: done`, `fix_severity` and `fix_severity_reason` filled in
5. Run `$SESSION_INFO eval-summary`. On failure → apply Blocking policy.
6. Present payload to the user (issue table + `fix_severity` summary).
7. Ask user:
   - **Deliver** → stop; parent runs `$SESSION_CONTROL ready-for-delivery`
   - **Continue editing** → write `workflow-state.md`: `current_state: Drafting` (preserve `evaluate_round`, `mode`, `product_ref`, `carry_forward_ref`); stop; parent enters **Step 4 — FreeEdit**

---

## E6 — Abandon Handler

Triggered when `evaluate-state.md: current_dimension: abandoned`.

Steps are order-strict:

1. Write `workflow-state.md`:
   - `current_state: Drafting`
   - `evaluate_round: M` (unchanged; next Evaluating entry increments to M+1)
   - `skip_evaluate_requested: false`
   - preserve `mode`, `product_ref`, `carry_forward_ref`

2. Stop — do not dispatch remaining dimensions

Hook validates `current_dimension: abandoned` before allowing the transition. `evaluate{M}/` and review files are retained as history.
