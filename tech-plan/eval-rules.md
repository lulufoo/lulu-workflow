---
rule-guard:
  globs:
    - "**/*.md"
---

# Evaluating Orchestration Rules

Loaded when parent routes to Evaluating Rules (user chose **Evaluate** from FreeEdit).
Follow this document exactly. Do not execute any evaluation step before reading it.

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.
`$SESSION_INFO` / `$SESSION_CONTROL` / `$EVAL_CONTROL` non-zero exit → apply Blocking.

---

## Step 1 — Entry

1. Run `$EVAL_CONTROL begin-eval-round`. Pin payload.
2. For each `dim` in `payload.dispatch`:
   - Execute **Step 2 — Single dimension** with `dim` and pinned payload.
   - If Step 2 exits to **Step 4 — Abandon Handler** → STOP.
3. When all dimensions complete → **Step 3 — Completion**.

---

## Step 2 — Single dimension

Inputs: `dim` (from Step 1 loop), pinned Step 1 payload.

1. Run `$EVAL_CONTROL begin-dimension --dim {dim}`. On failure → Blocking. Pin `dispatch_input`.

2. Dispatch `eval-runner` (`$SUBAGENT_TOOL`, `$SUBAGENT_AWAIT_SYNC`). Prompt:

```text
Load {$SKILL_ROOT}/tech-plan/eval-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input from step 1}
```

3. Await completion

4. Run `$EVAL_CONTROL check-dimension --dim {dim}`. Pin payload.
   - `payload.abandoned: true` → **Step 4 — Abandon Handler**, STOP
   - non-zero exit → Blocking, STOP
   - else (`outcome: complete`) → continue Step 1 loop

---

## Step 3 — Completion

After Step 1 loop completes:

1. Run `$EVAL_CONTROL complete-round`. On failure → Blocking. Pin payload.
2. Present payload to the user.
3. Ask user:
   - **Deliver** → stop; parent runs `$SESSION_CONTROL ready-for-delivery`
   - **Continue editing** → write `workflow-state.md`: `current_state: Drafting` (preserve `evaluate_round`, `mode`, `product_ref`, `carry_forward_ref`); stop; parent enters **Step 4 — FreeEdit** (parent SKILL)

---

## Step 4 — Abandon Handler

Triggered when `check-dimension` returns `abandoned: true` (or `evaluate-state.md: current_dimension: abandoned`).

1. Write `workflow-state.md`:
   - `current_state: Drafting`
   - `evaluate_round: M` (unchanged; use `M` from pinned Step 1 payload)
   - `skip_evaluate_requested: false`
   - preserve `mode`, `product_ref`, `carry_forward_ref`

2. Stop — do not dispatch remaining dimensions

Hook validates `current_dimension: abandoned` before allowing the transition.
