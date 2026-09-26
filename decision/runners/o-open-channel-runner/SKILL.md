---
name: decision/o-open-channel-runner
description: Internal runner for the Decision O gate.
meta-skill-version: 1.0.0
---

# o-open-channel-runner

Open the channel for existing Prior, Constraint, or Assumption context. Complete when the
user is ready to enter Q; empty capture is valid.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `O`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Must hold

| ID | Must hold |
|----|-----------|
| `G-invite` | Invite the user to share existing knowledge. Completeness is not required. An equivalent invite already this session satisfies this row. |
| `G-ready` | User confirms they are ready to proceed to Q. |

## Modes

`invite` → `confirm` may skip `listen`.

| Mode | When | Behavior |
|------|------|----------|
| `invite` | `G-invite` not yet satisfied | Issue the open-channel invite. |
| `listen` | User is sharing | Stay in channel. |
| `confirm` | Ready to ask for Q | Ask whether they are ready to proceed to Q. |
| `close` | User confirms ready | `$GATE_CONTROL gate-close --gate O --payload '{"user_confirmed": true}'` |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout O.

## Act

Loop Modes (Signals as above) until `close` succeeds.

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE O` · `GATE_FAILED O reason=<brief description>`
