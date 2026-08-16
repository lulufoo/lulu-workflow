---
name: eval-library
description: >
  Shared Eval orchestration for lulu-dev-workflow. Coordinates dimension probes
  and remediation through the caller's Eval control macro.
meta-skill-version: 1.0.0
---

# eval/SKILL.md

Shared Eval orchestration. Compose runs a full round; Decision runs only the
Probe control segment. The caller supplies `$EVAL_CONTROL` with its active
adapter configuration.

## Script Macros

| Macro | Command |
|-------|---------|
| `$EVAL_CONTROL` | Caller-supplied adapter-aware Eval control macro |

## Principles

- Findings require citable evidence. If evidence cannot be located, escalate; do not guess.
- A defective SoT is escalated, never silently repaired. A valid SoT that the artifact fails to reflect is remediated.
- Any non-zero control result is Blocking: stop, report it, and wait for user direction.
- Remediation processes one dimension at a time.

## Begin Eval

1. Run `$EVAL_CONTROL begin-eval-round`. Pin the result.
2. For each returned dimension, run **Single dimension (launch)** and pin its handle.
3. Await every pinned handle. Do not check a dimension before every handle completes.
4. For each returned dimension, run `$EVAL_CONTROL check-dimension --dim {dim}`.
   - If the result reports abandonment, run **Abandon Handler** and stop.
   - On a non-zero result, apply Blocking and stop.
5. A probe-only caller runs `$EVAL_CONTROL complete-probe-only` and stops.
6. A full-round caller continues to **Remediation**.

## Single dimension (launch)

1. Run `$EVAL_CONTROL begin-dimension --dim {dim}` and pin its returned operation context.
2. Dispatch `dimension-probe-runner` asynchronously with the pinned operation context and this instruction:

   ```text
   Load dimension-probe-runner/SKILL.md and follow its instructions.
   ```

3. Pin the returned handle and return immediately to **Begin Eval**.

## Remediation

1. Run `$EVAL_CONTROL begin-remediation` and pin the result.
2. Unless the result skips remediation, process each returned dimension serially:
   1. Run `$EVAL_CONTROL begin-dimension-remediation --dim {dim}` and pin `OPERATION_TOKEN` from its dispatch_input.
   2. Dispatch `remediation-runner` synchronously with that pinned context and this instruction:

      ```text
      Load remediation-runner/SKILL.md and follow its instructions.
      ```

   3. Run `$EVAL_CONTROL check-dimension-remediation --dim {dim}`.
   4. If the result reports abandonment, run **Abandon Handler** and stop.
3. Each dimension submits one complete application. Partial issue coverage is Blocking.
4. Run `$EVAL_CONTROL remediation-complete`.
5. Continue to **Completion**.

## Completion

1. Present the `remediation-complete` result.
2. If the caller’s adapter-config / handoff `policy_context.completion_mode` is
   `return_to_caller` (e.g. Compose Atomize Eval), **stop here** and return the
   `remediation-complete` payload to the caller. Do **not** present Accept L / Fix L /
   Re-evaluate / Deliver package.
3. Otherwise ask the user to choose:
   - **Accept L** — run `$L_STEP accept --confirm`; exit Eval.
   - **Fix L** — run `$L_STEP fix --confirm`; exit Eval.
   - **Re-evaluate** — run `$L_STEP re-evaluate --confirm`, then return to **Begin Eval**.

## Abandon Handler

1. Stop. Do not dispatch remaining dimensions.
2. Leave the L in Evaluating. Report abandonment and wait for user direction.
