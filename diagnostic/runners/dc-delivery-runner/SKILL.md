---
name: diagnostic/dc-delivery-runner
description: >-
  DC gate runner for diagnostic. Self-review, user confirmation, gate-close DC,
  and session delivery. Invoked by diagnostic/SKILL.md.
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
2. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
3. `$GATE_CONTROL check-delivery-ready` — fix every reported error before continuing
4. **AI Semantic Review** — read `$SKILL_DIR/session-invariants.yaml` and all existing `gate-payloads/*.json` under the session directory; compare against registers. On blocker: load RS runner, reopen at the checklist `reopen_gate` (earliest involved gate); do not present delivery content to the user
5. `$SESSION_INTEGRITY render` — generate `decision-doc.md`
6. Read `decision-doc.md` (G4 DC exception); present key sections in conversation; G8 user confirmation
7. `$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'`
8. `$GATE_CONTROL deliver`
9. Tell the user `$CTX.after_dc.user_message`
10. Return `GATE_COMPLETE DC Delivered`

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE DC Delivered`
