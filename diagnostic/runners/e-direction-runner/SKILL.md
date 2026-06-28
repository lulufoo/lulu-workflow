---
name: diagnostic/e-direction-runner
description: >-
  E gate runner for diagnostic. Executes direction exploration dialogue and
  gate-close E with incremental decision-doc write. Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# e-direction-runner

Execute **E — Direction Exploration** within a diagnostic session. Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/diagnostic`
- Gate contract: `$SKILL_DIR/gates/e-direction-exploration.md`
- `$CTX.gates.Q.status` must be `closed` (from resolve-context)

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Read `$CTX.domain_constraints.role.instruction` and follow it for all subsequent dialogue in this gate. Missing `role`: skip.
3. Execute E gate dialogue (2–3 directions, pros/cons, excluded, user choice; G1/G7/G8)
4. During dialogue: on identification hit → G0 runner → `G0_COMPLETE` → continue
5. After user confirms: `$GATE_CONTROL gate-close --gate E --payload '<json>'`
6. Return `GATE_COMPLETE E` to parent

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
