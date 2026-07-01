---
name: decision/q-problem-runner
description: >-
  Q gate runner for diagnostic. Executes problem clarification dialogue and
  gate-close Q with gate-payload write. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# q-problem-runner

Execute **Q — Problem Clarification** within a diagnostic session. Mechanical persistence via `$GATE_CONTROL` and `$REGISTER_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- Gate contract: `$SKILL_DIR/gates/q-problem-clarification.md`

- `$CTX.gates.O.status` must be `closed` (from resolve-context)

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin stdout JSON as `$CTX`
2. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
3. Execute Q gate dialogue (G1/G7/G8; on identification hit → G0 runner → `G0_COMPLETE` → continue)
4. After user confirms problem + constraints: `$GATE_CONTROL gate-close --gate Q --payload '<json>'`
5. Return `GATE_COMPLETE Q` to parent

## gate-close payload

```json
{
  "problem_statement": "<agreed problem>",
  "constraints": "<enumerated constraints>"
}
```

## Exit

On success:

```
GATE_COMPLETE Q
```

On failure:

```
GATE_FAILED Q reason=<brief description>
```
