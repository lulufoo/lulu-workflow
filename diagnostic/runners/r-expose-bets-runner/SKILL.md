---
name: diagnostic/r-expose-bets-runner
description: >-
  R gate runner for diagnostic. Risk classification, register updates, and R exit
  routing (Loop B, DC, or RS). Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# r-expose-bets-runner

Execute **R — Expose the Bets**. Updates assumption risk in registers and routes per exit path.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/r-expose-bets.md`
- `$CTX.gates.X.status` must be `closed`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Gate contract § Before entering — prior sign-off, then assumption coverage (G8)
3. Gate contract § Execute — risk + consequence (G8 confirm)
4. Select exit with user:
   - `rs` — known failure → RS runner (identify `reopen_gate`)
   - `loop_b` — uncertain assumptions → V
   - `dc` — all resolved → skip V/RR
5. `$GATE_CONTROL gate-close --gate R --payload '<json>'`
6. On `exit=rs`: load `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` with `reopen_gate`
7. Otherwise return `GATE_COMPLETE R exit=<loop_b|dc>`

## gate-close payload

```json
{
  "exit": "loop_b",
  "assumptions": [
    {"id": "A1", "risk": "H", "consequence": "..."},
    {"id": "A2", "risk": "L", "consequence": "..."}
  ]
}
```

RS exit:

```json
{
  "exit": "rs",
  "reopen_gate": "D",
  "assumptions": [{"id": "A1", "risk": "H", "consequence": "..."}]
}
```

- `exit`: `rs` | `loop_b` | `dc`
- `loop_b` / `dc`: marks all pending **prior** entries `verified`; `dc` also marks pending assumptions `verified`

## Exit

`GATE_COMPLETE R exit=loop_b|dc` · `GATE_COMPLETE R exit=rs reopen_gate=<G>` → RS runner
