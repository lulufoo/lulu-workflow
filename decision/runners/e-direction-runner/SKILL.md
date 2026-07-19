---
name: decision/e-direction-runner
description: >-
  E gate runner for decision. Executes direction exploration dialogue and
  gate-close E with gate-payload write. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# e-direction-runner

Execute **E — Direction Exploration** within a decision session. Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- Gate contract: `$SKILL_DIR/gates/e-direction-exploration.md`
- `$CTX.gates.GL.status` must be `closed` (from resolve-context)
- `$CTX.gl` must be present when GL is closed

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. If `$CTX.gates.E.status == stale`: follow `$SKILL_DIR/references/stale-gate-update.md` then return `GATE_COMPLETE E`
3. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. Gate contract § Before entering — consult `$CTX.gl` (T2/T4) before proposing directions
5. Execute E gate dialogue (2–3 directions, pros/cons, excluded, user choice; G1/G7/G8)
6. During dialogue: on identification hit → G0 runner → `G0_COMPLETE` → continue; on G9 hit → RS runner
7. After user confirms: `$GATE_CONTROL gate-close --gate E --payload '<json>'`
8. Return `GATE_COMPLETE E` to parent

## gate-close payload

```json
{
  "directions": [
    {
      "name": "Option A",
      "approach": "...",
      "pros": "...",
      "cons": "...",
      "recommended": true
    }
  ],
  "excluded": [{"name": "...", "reason": "..."}],
  "user_choice": "<chosen direction>"
}
```

Requires **≥2** directions in `directions`.

## Exit

On success:

```
GATE_COMPLETE E
```

On failure:

```
GATE_FAILED E reason=<brief description>
```
