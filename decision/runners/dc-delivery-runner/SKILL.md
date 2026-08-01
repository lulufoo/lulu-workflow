---
name: decision/dc-delivery-runner
description: >-
  DC gate runner for decision. Self-review, user confirmation, gate-close DC,
  and session delivery. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# dc-delivery-runner

Execute **DC — Delivery Confirmation**. Confirm delivery readiness via control CLI, then deliver.

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
   - Do **not** run that file's step 4 (`gate-close`) or step 5 (`GATE_COMPLETE`) — DC close stays at step 8 after delivery checks
   - Then continue from step 3 below
3. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. `$GATE_CONTROL check-delivery-ready` — fix every reported error before continuing
5. **AI Semantic Review** (required) — read `session-invariants.yaml` + `gate-payloads/*.json`; cross-check `$CTX.registers`. Blocker → RS runner (earliest checklist `realign_gate`); do not present delivery content.
6. `$SESSION_INTEGRITY render` — generate `decision-doc.md`
7. Read `decision-doc.md`; present key sections in conversation; explicitly list any `Class=implementation` Handoff lines (remind only); user confirmation
8. `$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'`
9. `$GATE_CONTROL deliver`
10. Tell the user `$CTX.after_dc.user_message`. If Active is a nested holder session (`main/` / `Dx/` under approach), also state that only this **node session** is Delivered — stage export waits for the holder seal (`confirm-seal`).
11. Return `GATE_COMPLETE DC Delivered`

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE DC Delivered`
