---
name: decision/r-expose-bets-runner
description: >-
  R gate runner for decision. Risk classification, register updates, and R exit
  routing (Loop B, DC, or RS). Invoked by decision/SKILL.md.
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
2. If `$CTX.gates.R.status == stale`:
   - Follow `$SKILL_DIR/references/stale-gate-update.md` steps 1–4 only (three-part update + user confirm + `gate-close`; payload must include `exit`, and `realign_gate` when `exit=rs`)
   - Do **not** follow that file's step 5 return — go to step 8 below (same exit handoff as non-stale)
3. Otherwise (not stale) — read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. Gate contract § Before entering — prior sign-off, assumption coverage, and `$CTX.gl.exchanges` (prefer `gap_check` / risk-narrative / confirmation intents)
5. Gate contract § Execute — risk + `risk_class` + consequence on the full table (user confirm; never classify at G0)
6. Select exit with user:
   - `rs` — known failure → RS runner (identify `realign_gate`)
   - `loop_b` — uncertain assumptions, any `pending`, or any `implementation` → RR
   - `dc` — all `decision` and resolved → skip RR (**forbidden** if any `implementation` or `pending`)
7. `$GATE_CONTROL gate-close --gate R --payload '<json>'`
8. On `exit=rs`: load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` with `realign_gate`
9. Otherwise return `GATE_COMPLETE R exit=<loop_b|dc>`

## gate-close payload

```json
{
  "exit": "loop_b",
  "assumptions": [
    {"id": "A1", "risk": "H", "risk_class": "decision", "consequence": "..."},
    {"id": "A2", "risk": "H", "risk_class": "implementation", "consequence": "..."},
    {"id": "A3", "risk": "L", "risk_class": "pending", "consequence": "..."}
  ]
}
```

RS exit:

```json
{
  "exit": "rs",
  "realign_gate": "D",
  "assumptions": [{"id": "A1", "risk": "H", "risk_class": "decision", "consequence": "..."}]
}
```

- `exit`: `rs` | `loop_b` | `dc`
- each assumption requires `risk`, `risk_class`, `consequence`
- `exit=dc` forbids `risk_class` of `pending` or `implementation`
- `loop_b` / `dc`: marks all pending **prior** entries `verified`; `dc` also marks pending assumptions `verified`

## Exit

`GATE_COMPLETE R exit=loop_b|dc` · `GATE_COMPLETE R exit=rs realign_gate=<G>` → RS runner
