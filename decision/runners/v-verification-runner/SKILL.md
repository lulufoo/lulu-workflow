---
name: decision/v-verification-runner
description: >-
  V gate runner for decision. Verification column updates and Loop B exit
  routing (RR or DC). Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# v-verification-runner

Execute **V — Verification**. Updates assumption Verification in registers and routes per exit path.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/v-verification.md`
- `$CTX.gates.R.status` must be `closed`
- `$CTX.skipped_gates` must be empty

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. If `$CTX.gates.V.status == stale`: follow `$SKILL_DIR/references/stale-gate-update.md` then return `GATE_COMPLETE V exit=<from payload>`
3. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. Resolve every `risk_class=pending` with the user → `decision` or `implementation` (gate contract § Execute 0)
5. Assign Verification by class: decision H/tracked → full Method/Release; decision M/L → `Accepted` (user batch confirm); implementation → `Handoff: …`
6. Select exit with user: `rr` (decision RR-scope) or `dc` (no decision RR-scope; handoffs done)
7. `$GATE_CONTROL gate-close --gate V --payload '<json>'`
8. Return `GATE_COMPLETE V exit=<rr|dc>`

## gate-close payload

```json
{
  "exit": "rr",
  "batch_confirmed": true,
  "assumptions": [
    {
      "id": "A1",
      "risk": "H",
      "risk_class": "decision",
      "verification": "Method: load test / Owner: QA / Timing: pre-release / Release condition: p99 < 200ms"
    },
    {
      "id": "A2",
      "risk": "H",
      "risk_class": "implementation",
      "verification": "Handoff: impl team / post-merge acceptance"
    },
    {
      "id": "A3",
      "risk": "L",
      "risk_class": "decision",
      "verification": "Accepted",
      "release_tracking": false
    }
  ]
}
```

- `exit`: `rr` | `dc`
- `batch_confirmed`: required `true` for `dc` exit (M/L batch confirmation)
- No `pending` at close; `implementation` + `release_tracking` forbidden
- RR-scope = `decision` AND (H or `release_tracking`); `dc` forbidden if any RR-scope remain
- V close marks `implementation` → `verified` (handoff)

## Exit

`GATE_COMPLETE V exit=rr` or `GATE_COMPLETE V exit=dc`
