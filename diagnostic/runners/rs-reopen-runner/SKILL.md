---
name: diagnostic/rs-reopen-runner
description: >-
  RS subroutine for diagnostic. Mechanical gate/doc invalidation and register
  batch relabeling after reopen trigger. Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# rs-reopen-runner

Execute **RS — Reopen State Handler**. Clears downstream gate conclusions and relabels registers per user confirmation.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/rs-reopen-state-handler.md`
- Reopen gate `G` identified (Q / E / D / X) — from trigger context or user

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`; use on-disk decision-doc as baseline (not conversation memory)
2. Step 1 — confirm reopen gate `G` with user (G8)
3. `$GATE_CONTROL invalidate-from --gate <G>` — mechanical gate-state + doc zone reset
4. Step 3 — propose 3-state labeling for all register entries; user confirms (G8)
5. `$REGISTER_CONTROL register-batch-apply --operations '<json array>'`
6. `$REGISTER_CONTROL sync-registers-to-doc`
7. `$GATE_CONTROL resolve-context` — refresh Reply Header
8. Return `RS_COMPLETE reenter=<G>` — load gate `G` runner next

## register-batch-apply operations

```json
[
  {"id": "P2", "action": "set_state", "state": "pending"},
  {"id": "A3", "action": "set_state", "state": "verified"},
  {"id": "A4", "action": "delete"}
]
```

- `set_state`: `pending` | `verified` (maps to `[待验证]` / `[已验证]`)
- `delete` or `set_state: invalidated` → remove entry (`[失效]`)

## Exit

`RS_COMPLETE reenter=Q` (or E / D / X)
