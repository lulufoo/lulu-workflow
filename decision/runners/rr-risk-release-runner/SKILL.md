---
name: decision/rr-risk-release-runner
description: >-
  RR gate runner for decision Loop B. Risk release verification and RR exit
  routing (DC, return R, or Human Decision). Invoked by decision/SKILL.md.
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
- Scope: `risk_class=decision` AND (High-risk OR `release_tracking`) only — never `implementation`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. If `$CTX.gates.RR.status == stale`:
   - Follow `$SKILL_DIR/references/stale-gate-update.md` steps 1–4 only (three-part update + user confirm + `gate-close`; payload must include `exit`)
   - Do **not** follow that file's step 5 return — go to step 7 below (same exit handoff as non-stale)
3. Otherwise (not stale) — read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. For each RR-scope item: check Release condition vs verification result (user confirm per item)
5. Select exit with user:
   - `dc` — all scope items released, no new pending from V/RR
   - `return_r` — all scope items released, new pending assumptions from V/RR
   - `human_decision` — any scope item still unreleased
6. `$GATE_CONTROL gate-close --gate RR --payload '<json>'`
7. On `exit=human_decision`: load `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md`
8. Otherwise return `GATE_COMPLETE RR exit=<dc|return_r>`

## gate-close payload

```json
{
  "exit": "dc",
  "assumptions": [
    {"id": "A1", "released": true}
  ]
}
```

- Include only RR-scope assumptions (`decision` ∩ (H-risk or `release_tracking`))
- `released: true` → Status `[已验证]` in registers/doc

## Exit

`GATE_COMPLETE RR exit=dc|return_r` · `exit=human_decision` → `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md`
