---
name: decision/e-direction-runner
description: Internal runner for the Decision E gate.
meta-skill-version: 1.0.0
---

# e-direction-runner

Settle a direction for the locked problem and GL intent. Complete when the user
explicitly accepts it.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `E`, `$CTX.gl` present).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.
- Apply `$SKILL_ROOT/shared/references/ask-protocol.md` to every E question.

## Must hold

| ID | Must hold |
|----|-----------|
| `G-settled-direction` | For the locked Q and GL intent, 2–3 directions with trade-offs, one recommendation, and exclusions (or none) are ready; the user explicitly accepts one or an alternative. |

Use locked Q, `$CTX.gl.exchanges`, related Prior / Assumption entries, and this
gate's dialogue. Stay at direction trade-offs; do not reopen GL intent or enter
implementation planning.

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `define` | Candidate set incomplete | Complete it; use Ask Protocol for any missing input. |
| `align` | Candidate set ready; acceptance missing | Present it with one recommendation; obtain acceptance or an alternative. |
| `settle` | `G-settled-direction` holds | `$GATE_CONTROL gate-close --gate E --payload '<json>'`. |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout E.

## Act

1. If `$CTX.gates.E.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE E`,
   and skip the loop.
2. Loop Modes (Signals as above) until `settle` succeeds.

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

Validation: `$GATE_CONTROL --help`.

## Exit

`GATE_COMPLETE E` · `GATE_FAILED E reason=<brief description>`
