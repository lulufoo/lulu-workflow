---
name: diagnostic/v-verification-runner
description: >-
  V gate runner for diagnostic. Verification column updates and Loop B exit
  routing (RR or DC). Invoked by diagnostic/SKILL.md.
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
2. For each assumption: assign Verification per risk (H → full format; M/L → `Accepted` after G8 batch confirm)
3. Select exit with user: `rr` (high-risk or release-tracking items) or `dc` (all M/L accepted, no RR needed)
4. `$GATE_CONTROL gate-close --gate V --payload '<json>'`
5. Return `GATE_COMPLETE V exit=<rr|dc>`

## gate-close payload

```json
{
  "exit": "rr",
  "batch_confirmed": true,
  "assumptions": [
    {
      "id": "A1",
      "risk": "H",
      "verification": "Method: load test / Owner: QA / Timing: pre-release / Release condition: p99 < 200ms"
    },
    {
      "id": "A2",
      "risk": "L",
      "verification": "Accepted",
      "release_tracking": false
    }
  ]
}
```

- `exit`: `rr` | `dc`
- `batch_confirmed`: required `true` for `dc` exit (G8 M/L batch confirmation)
- High-risk or `release_tracking: true` → full Verification format; `dc` exit forbidden if any exist

## Exit

`GATE_COMPLETE V exit=rr` or `GATE_COMPLETE V exit=dc`
