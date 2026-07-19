---
name: decision/gl-grill-runner
description: >-
  GL gate runner for decision. Grill-style decision-domain intent probe between
  Q and E; gate-close GL with exchanges payload. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# gl-grill-runner

Execute **GL — Grill**. Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- Gate contract: `$SKILL_DIR/gates/gl-grill.md`
- `$CTX.gates.Q.status` must be `closed`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. If `$CTX.gates.GL.status == stale`: follow `$SKILL_DIR/references/stale-gate-update.md` then return `GATE_COMPLETE GL`
3. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. Gate contract § Before entering / § Execute (framework pass). HARD: do not call `gate-close` until framework pass holds (reasoned T1–T4 coverage, Q intact, G8). Unjustified all-na is not a pass.
5. During dialogue: on identification hit → G0 runner → `G0_COMPLETE` → continue; on G9 hit → RS runner
6. `$GATE_CONTROL gate-close --gate GL --payload '<json>'`
7. Return `GATE_COMPLETE GL`

## gate-close payload

```json
{
  "exchanges": [
    {
      "topic": "T1",
      "question": "<question>",
      "answer": "<user answer>",
      "na": false
    }
  ],
  "user_confirmed": true
}
```

- `topic` ∈ `T1`|`T2`|`T3`|`T4`; every topic at least once (conclusion or `na: true`)
- Mechanical validation is CLI-only; framework pass is this runner's responsibility

## Exit

`GATE_COMPLETE GL` or `GATE_FAILED GL reason=...`
