---
name: diagnostic/dc-delivery-runner
description: >-
  DC gate runner for diagnostic. Self-review, user confirmation, gate-close DC,
  and session delivery. Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# dc-delivery-runner

Execute **DC — Delivery Confirmation**. Decision-doc is already on disk; confirm and deliver.

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
2. `$GATE_CONTROL check-delivery-ready` — fix any reported errors before presenting
3. Self-review decision-doc on disk (completeness / consistency per gate contract)
4. Present key sections in conversation; G8 user confirmation
5. `$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'`
6. `$GATE_CONTROL deliver`
7. Return `GATE_COMPLETE DC Delivered`

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE DC Delivered` — Reply Header stops after Delivered (G4)
