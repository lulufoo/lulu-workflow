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

**Remediation serial** — Steps 3–4 always process dimensions **one at a time** (sync runner). Multiple dimensions may share the same `REMEDIATION_TARGET_PATH`.

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

2. Dispatch `eval-probe-runner` (`$SUBAGENT_TOOL`, `$SUBAGENT_AWAIT_ASYNC`). Prompt:

```text
Load {$SKILL_ROOT}/eval/eval-probe-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input from Step 2.1}
```

3. Pin `{dim}_handle` from dispatch return value (agent id).

4. **Return to Step 1 immediately** — do not await; do not run `check-dimension`.

---

## Step 3 — Artifact Remediation

1. Run `$EVAL_CONTROL begin-artifact-remediation`. On failure → Blocking. Pin payload.
   - If `payload.skip: true` → go to Step 3.4 (no per-dim dispatch).
   - Else pin `payload.dispatch` (dims with pending WO-*).

2. **Per dimension (serial):** For each `dim` in `payload.dispatch`:
   - Run `$EVAL_CONTROL begin-dimension-artifact-remediation --dim {dim}`. On failure → Blocking.
     - Success stdout is **plain text**. Pin as `dispatch_input`.
   - Dispatch `eval-artifact-remediation-runner` (`$SUBAGENT_AWAIT_SYNC`). Prompt:

```text
Load {$SKILL_ROOT}/eval/eval-artifact-remediation-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input}
```

   - Run `$EVAL_CONTROL check-dimension-artifact-remediation --dim {dim}`. On failure → Blocking.

3. (Omit Step 3.2 when `skip: true`.)

4. Run `$EVAL_CONTROL artifact-remediation-complete`. On failure → Blocking.

5. Proceed to **Step 4 — SoT Remediation**.

---

## Step 4 — SoT Remediation

1. Run `$EVAL_CONTROL begin-sot-remediation`. On failure → Blocking. Pin payload.
   - If `payload.skip: true` → go to Step 4.4.
   - Else pin `payload.dispatch`.

2. **Per dimension (serial):** For each `dim` in `payload.dispatch`:
   - Run `$EVAL_CONTROL begin-dimension-sot-remediation --dim {dim}`. On failure → Blocking.
     - Success stdout is **plain text**. Pin as `dispatch_input`.
   - Dispatch `eval-sot-remediation-runner` (`$SUBAGENT_AWAIT_SYNC`). Prompt:

```text
Load {$SKILL_ROOT}/eval/eval-sot-remediation-runner/SKILL.md and follow its instructions.

## Input
{dispatch_input}
```

   - Run `$EVAL_CONTROL check-dimension-sot-remediation --dim {dim}`.
     - `payload.abandoned: true` → **Step 6 — Abandon Handler**, STOP
     - non-zero exit → Blocking, STOP

3. (Omit Step 4.2 when `skip: true`.)

4. Run `$EVAL_CONTROL sot-remediation-complete`. On failure → Blocking.

5. Proceed to **Step 5 — Completion**.

---

## Step 5 — Completion

1. Run `$EVAL_CONTROL complete-round`. On failure → Blocking. Pin payload.
2. Present payload to the user.
3. Ask user:
   - **Deliver** → exit eval-rules (Deliver branch)
   - **Continue editing** → Run `$SESSION_CONTROL resume-after-eval`. On failure → Blocking. Pin payload.; exit eval-rules (Continue editing branch)
   - **Re-evaluate** → re-enter **Step 1 — Begin Eval**

---

## Step 6 — Abandon Handler

1. Run `$SESSION_CONTROL abandon-evaluation`. On failure → Blocking. Pin payload.
2. Stop — do not dispatch remaining dimensions.
