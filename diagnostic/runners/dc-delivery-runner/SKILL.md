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
2. Apply Role from `$CTX.domain_constraints` if present
3. `$GATE_CONTROL check-delivery-ready` — fix every reported error before presenting
4. Present key sections in conversation (from `$CTX` / gate contract); G8 user confirmation
5. `$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'`
6. `$GATE_CONTROL deliver`
7. Tell the user `$CTX.after_dc.user_message`
8. Return `GATE_COMPLETE DC Delivered`

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE DC Delivered`
