---
rule-guard:
  globs:
    - "**/*.md"
---

# Evaluating Orchestration Rules

Loaded when parent routes to Evaluating Rules (user chose **Evaluate** from FreeEdit).
Follow this document exactly. Do not execute any evaluation step before reading it.

`$SESSION_INFO` / `$SESSION_CONTROL` / `$EVAL_CONTROL` non-zero exit → Blocking (parent SKILL).

---

## Phase 1 — Initialize (E1)

1. Run `$SESSION_CONTROL start-evaluating`.
2. Read `evaluate-state.md` → confirm `phase: evaluate` and dimension fields match `mode`.
3. Proceed to Phase 2.

---

## Phase 2 — Per-dimension loop (E2)

1. Run `$SESSION_INFO eval-dispatch`. Pin payload.
2. For each `dim` in `payload.dispatch`:
   - Execute **Phase 3 — Single dimension** with `dim` and pinned payload.
   - If Phase 3 exits to **E6** → STOP.
3. When all dimensions complete → Phase 4.

---

## Phase 3 — Single dimension (E3)

Inputs: `dim` (from E2 loop), pinned E2 payload.

1. Run `$EVAL_CONTROL begin-dimension --dim {dim}`. On failure → Blocking. Pin `dispatch_input`.

2. Dispatch `eval-runner` (`$SUBAGENT_TOOL`, `$SUBAGENT_AWAIT_SYNC`). Prompt:

```text
Load {$SKILL_ROOT}/tech-plan/eval-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input from step 1}
```

3. Await completion

4. Read `evaluate-state.md` → check `current_dimension`:
   - if `abandoned` → **E6 Abandon Handler**, STOP
   - else → verify `{dim}_status: complete`

---

## Phase 4 — Completion (E4)

After E2 loop completes (use `M` from pinned E2 payload):

1. Read all completed review files (`evaluate{M}/tech-review-e{M}1.md`, `e{M}2.md`, `e{M}3.md`) — only those that exist
2. Collect the `Severity` column of every issue row; determine `fix_severity` as the highest level found (critical > medium > minor); if all ignored, use `minor`
3. Write `fix_severity_reason` (one sentence citing the most severe issue)
4. Write `evaluate-state.md`: `current_dimension: done`, `fix_severity` and `fix_severity_reason` filled in
5. Run `$SESSION_INFO eval-summary`.
6. Present `eval-summary` payload to the user.
7. Ask user:
   - **Deliver** → stop; parent runs `$SESSION_CONTROL ready-for-delivery`
   - **Continue editing** → write `workflow-state.md`: `current_state: Drafting` (preserve `evaluate_round`, `mode`, `product_ref`, `carry_forward_ref`); stop; parent enters **Step 4 — FreeEdit**

---

## E6 — Abandon Handler

Triggered when `evaluate-state.md: current_dimension: abandoned`.

1. Write `workflow-state.md`:
   - `current_state: Drafting`
   - `evaluate_round: M` (unchanged; use `M` from pinned E2 payload)
   - `skip_evaluate_requested: false`
   - preserve `mode`, `product_ref`, `carry_forward_ref`

2. Stop — do not dispatch remaining dimensions

Hook validates `current_dimension: abandoned` before allowing the transition.
