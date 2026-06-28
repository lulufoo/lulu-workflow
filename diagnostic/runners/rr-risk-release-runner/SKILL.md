---
name: diagnostic/rr-risk-release-runner
description: >-
  RR gate runner for diagnostic Loop B. Risk release verification and RR exit
  routing (DC, return R, or Human Decision). Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# rr-risk-release-runner

Execute **RR — Risk Release**. Checks release conditions and updates assumption Status in registers.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/rr-risk-release.md`
- `$CTX.gates.V.status` must be `closed`
- Scope: High-risk assumptions + user-flagged `release_tracking` items only

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Read `$CTX.domain_constraints.role.instruction` and follow it for all subsequent dialogue in this gate. Missing `role`: skip.
3. For each RR-scope item: check Release condition vs verification result (G8 confirm per item)
4. Select exit with user:
   - `dc` — all scope items released, no new pending from V/RR
   - `return_r` — all scope items released, new pending assumptions from V/RR
   - `human_decision` — any scope item still unreleased
5. `$GATE_CONTROL gate-close --gate RR --payload '<json>'`
6. Return `GATE_COMPLETE RR exit=<dc|return_r|human_decision>` or load Human Decision runner

## gate-close payload

```json
{
  "exit": "dc",
  "assumptions": [
    {"id": "A1", "released": true}
  ]
}
```

- Include only RR-scope assumptions (H-risk or `release_tracking`)
- `released: true` → Status `[已验证]` in registers/doc

## Exit

`GATE_COMPLETE RR exit=dc|return_r` · `GATE_COMPLETE RR exit=human_decision` → `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md`
