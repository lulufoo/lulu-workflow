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

## Step 1 — Begin Eval

1. Run `$EVAL_CONTROL begin-eval-round`. On failure → Blocking. Pin payload.

2. **Launch phase:** For each `dim` in `payload.dispatch`:
   - Execute **Step 2 — Single dimension (launch)** with `dim` and pinned payload.
   - Pin `{dim}_handle` from Step 2 return.

3. **Await phase:** Await completion notifications for all pinned `{dim}_handle` values. Each handle implies runner finished review **and** `$EVAL_CONTROL finish-dimension-probe` succeeded for that dim. Do not run `check-dimension` until every handle has completed.

4. **Check phase:** For each `dim` in `payload.dispatch`:
   - Run `$EVAL_CONTROL check-dimension --dim {dim}`. Pin payload.
   - `payload.abandoned: true` → **Step 6 — Abandon Handler**, STOP
   - non-zero exit → Blocking, STOP
   - else (`outcome: probed`) → continue

5. Run `$EVAL_CONTROL probe-complete`. On failure → Blocking.

6. Proceed to **Step 3 — Artifact Remediation**.

---

## Step 2 — Single dimension (launch)

Inputs: `dim`, pinned Step 1 payload.

1. Run `$EVAL_CONTROL begin-dimension --dim {dim}`. On failure → Blocking.
   - Success stdout is **plain text** (not JSON). Pin entire stdout as `dispatch_input`.

2. Dispatch `eval-runner` (`$SUBAGENT_TOOL`, `$SUBAGENT_AWAIT_ASYNC`). Prompt:

```text
Load {$SKILL_ROOT}/tech-plan/eval-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input from Step 2.1}
```

3. Pin `{dim}_handle` from dispatch return value (agent id).

4. **Return to Step 1 immediately** — do not await; do not run `check-dimension`.

---

## Step 3 — Artifact Remediation

1. Run `$EVAL_CONTROL begin-artifact-remediation`. On failure → Blocking.
   - Success stdout is **JSON**. Pin payload.
   - If `payload.skip: true` → proceed to **Step 4** without dispatch.
   - Else pin `payload.dispatch_input` (plain-text block inside JSON) for Step 3.2.

2. Dispatch `eval-artifact-remediation-runner` (`$SUBAGENT_AWAIT_SYNC`). Prompt:

```text
Load {$SKILL_ROOT}/tech-plan/eval-artifact-remediation-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input from Step 3.1}
```

3. Run `$EVAL_CONTROL check-artifact-remediation`. On failure → Blocking.

---

## Step 4 — SoT Remediation

1. Run `$EVAL_CONTROL begin-sot-remediation`. On failure → Blocking.
   - Success stdout is **JSON**. Pin payload.
   - If `payload.skip: true` → proceed to **Step 5** without dispatch.
   - Else pin `payload.dispatch_input` (plain-text block inside JSON) for Step 4.2.

2. Dispatch `eval-sot-remediation-runner` (`$SUBAGENT_AWAIT_SYNC`). Prompt:

```text
Load {$SKILL_ROOT}/tech-plan/eval-sot-remediation-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input from Step 4.1}
```

3. Run `$EVAL_CONTROL check-sot-remediation`.
   - `payload.abandoned: true` → **Step 6 — Abandon Handler**, STOP
   - non-zero exit → Blocking, STOP

---

## Step 5 — Completion

1. Run `$EVAL_CONTROL complete-round`. On failure → Blocking. Pin payload.
2. Present payload to the user.
3. Ask user:
   - **Deliver** → exit eval-rules (Deliver branch)
   - **Continue editing** → Run `$EVAL_CONTROL resume-drafting`. On failure → Blocking. Pin payload.; exit eval-rules (Continue editing branch)
   - **Re-evaluate** → re-enter **Step 1 — Begin Eval**

---

## Step 6 — Abandon Handler

1. Run `$SESSION_CONTROL abandon-evaluation`. On failure → Blocking. Pin payload.
2. Stop — do not dispatch remaining dimensions.
