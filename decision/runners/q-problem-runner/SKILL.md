---
name: decision/q-problem-runner
description: Internal runner for the Decision Q gate.
meta-skill-version: 1.0.0
---

# q-problem-runner

Produce a clear problem definition. Complete when the user confirms the
problem statement.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `Q`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.
- Before the first probe, read `$SKILL_ROOT/shared/references/ask-protocol.md`;
  apply it to every probe.

## Problem

| ID | Must hold |
|----|-----------|
| `G-problem` | A clear problem definition: what triggered this decision, and what problem we are solving. |

A merely stated problem claim is not a pass. Evaluate from the conversation so far.

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `probe` | `G-problem` not yet clear | Apply ask-protocol. |
| `summarize` | `G-problem` clear | Restate the problem once; ask if correct. |
| `close` | User confirms summarize | `$GATE_CONTROL gate-close --gate Q --payload '<json>'` |

If the user rejects the summary: treat the denied point as a gap → `probe`.

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout Q.

## Act

1. If `$CTX.gates.Q.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE Q`,
   and skip the loop.
2. Loop Modes (Signals as above) until `close` succeeds.

## gate-close payload

```json
{"problem_statement": "<agreed problem>"}
```

## Exit

`GATE_COMPLETE Q` · `GATE_FAILED Q reason=<brief description>`
