---
name: diagnostic/o-open-channel-runner
description: >-
  O gate runner for diagnostic. Open channel prior dump and gate-close O before Q.
  Invoked by diagnostic/SKILL.md.
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

- `$SKILL_DIR` = `$SKILL_ROOT/diagnostic`
- Gate contract: `$SKILL_DIR/gates/o-open-channel.md`
- `$CTX.active_gate` must be `O` (from resolve-context)

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Apply Role + holder Context Loading per kernel Domain Constraints HARD-GATE
3. Open channel dialogue + G0 per parent § Parallel Registers
4. After user confirms ready for Q (G8): `$GATE_CONTROL gate-close --gate O --payload '{"user_confirmed": true}'`
5. Return `GATE_COMPLETE O` to parent

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
