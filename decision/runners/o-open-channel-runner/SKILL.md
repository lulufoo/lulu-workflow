---
name: decision/o-open-channel-runner
description: Internal runner for the Decision O gate.
meta-skill-version: 1.0.0
---

# o-open-channel-runner

Open the channel for existing User Prior or Assumption context. Complete when the
user is ready to enter Q; empty capture is valid.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `O`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Channel

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

## Routes

- G9 hit: load RS runner → after return, resume O dialogue.
- G0 hit: load G0 runner → `G0_COMPLETE` → resume O dialogue.

## Act

Loop Modes (Routes as above) until `close` succeeds.

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE O` · `GATE_FAILED O reason=<brief description>`
