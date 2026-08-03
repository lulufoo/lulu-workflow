---
name: decision/dc-delivery-runner
description: >-
  DC gate runner for decision. Delivery-ready check, formal Eval, user
  confirmation, gate-close DC, and session complete. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# dc-delivery-runner

Execute **DC — Delivery Confirmation** (session completion gate). Confirm
readiness via control CLI, run Decision Eval, then `$GATE_CONTROL complete`.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/dc-delivery-confirmation.md`
- Entry: R exit `dc`, V exit `dc`, or RR exit `dc`
- `$CTX.active_gate` must be `DC`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. If `$CTX.gates.DC.status == stale`:
   - Follow `$SKILL_DIR/references/stale-gate-update.md` steps 1–3 only (change points / old disposition / update proposal; user confirm on that proposal if needed)
   - Do **not** run that file's step 4 (`gate-close`) or step 5 (`GATE_COMPLETE`) — DC close stays after readiness + Eval + user confirm
   - Then continue from step 3 below
3. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. `$GATE_CONTROL check-delivery-ready` — fix every reported error before continuing
5. **Decision Eval** (required; replaces AI Semantic Review):
   1. `$DEC_EVAL check-rounds` — if `hard_blocked: true` → stop; do not DC close; tell user max Eval rounds exhausted (must RS strategy change or abort)
   2. `$EVAL_CONTROL begin-eval-round` — binds `decision-eval-target.md` and enters evaluating
   3. For `decision-consistency` in `dispatch`: `$EVAL_CONTROL begin-dimension` → pin stdout as `dispatch_input` → `$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_SYNC` dispatch `eval/eval-probe-runner` (prompt shape: `eval/eval-rules.md` Step 2) → `$EVAL_CONTROL check-dimension`. Blocker issues must set `realign_gate` (`E`/`D`/`X`).
   4. `$EVAL_CONTROL probe-complete` — pin `total_issues`
   5. Skip artifact/SoT remediation (no `eval/eval-rules.md` Steps 3–4)
   6. If `total_issues > 0`:
      - Summarize issues (`dimension_id`, `location`, `description`, `realign_gate`)
      - `$DEC_EVAL fail-exit --issues-json '<array>'` — pin earliest `realign_gate`, `hard_blocked`
      - If `hard_blocked` → stop (no DC close)
      - Else load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` at `realign_gate` (earliest); do not present completion content
   7. If `total_issues == 0`: `$DEC_EVAL pass-exit` → continue
6. `$SESSION_INTEGRITY render` — generate delivery `decision-doc.md`
7. Read `decision-doc.md`; present key sections in conversation; explicitly list any `Class=implementation` Handoff lines (remind only); user confirmation
8. `$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'`
9. `$GATE_CONTROL complete`
10. Tell the user `$CTX.after_dc.user_message`. If Active is a nested holder session (`main/` / `Dx/` under approach), also state that only this **node session** is **Completed** — stage **Delivered** waits for the holder `$APPROACH_DELIVER`.
11. Return `GATE_COMPLETE DC Completed`

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE DC Completed`
