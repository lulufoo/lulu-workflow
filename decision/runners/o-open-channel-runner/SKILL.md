---
name: decision/o-open-channel-runner
description: >-
  O gate runner for decision. Open channel prior dump and gate-close O before Q.
  Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# o-open-channel-runner

Execute **O — Open Channel** (LoopA entry). Captures optional User Prior / Assumption entries before Q.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- Gate contract: `$SKILL_DIR/gates/o-open-channel.md`
- `$CTX.active_gate` must be `O` (from resolve-context)

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
3. Context loading per `$SKILL_DIR/gates/o-open-channel.md`
4. Open channel dialogue — on identification hit → G0 runner → `G0_COMPLETE` → continue
5. After user confirms ready for Q (G8): `$GATE_CONTROL gate-close --gate O --payload '{"user_confirmed": true}'`
6. Return `GATE_COMPLETE O` to parent

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

On success:

```
GATE_COMPLETE O
```

On failure:

```
GATE_FAILED O reason=<brief description>
```
