---
name: decision/d-decision-runner
description: Internal runner for the Decision D gate.
meta-skill-version: 1.0.0
---

# d-decision-runner

Define the selected direction's rationale, scope and exclusions, and landing
approach. Complete when the user confirms all three.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |

Subcommand contracts: module docstring / `--help`.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `D`, `$CTX.gl` present).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Reconcile

Before discussing a decision:

1. Read `$E` (the persisted E payload), `$CTX.registers.prior`, and
   `$CTX.gl.exchanges` in full.
2. Compare GL confirmation and operational intents with the chosen E direction
   and intended scope.
3. Compare every Prior with the chosen E direction and intended scope.
4. Surface and resolve every GL or Prior conflict explicitly in the Decision
   Rationale.

## Establish

| ID | Must establish |
|----|----------------|
| `G-rationale` | The chosen direction, its E trade-offs, and why alternatives are excluded. |
| `G-scope` | What the decision covers and explicit exclusions. |
| `G-landing` | The in-scope must-do chunks, their roles, dependencies, and order or parallelism. This is decision-level landing, not a work breakdown, schedule, or staffing plan. |

All three established; exclusions explicit; rationale references E trade-offs,
reconciles GL intents, and addresses every `concern` and `excluded` Prior (or
states that no such Prior exists); the user confirms.

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `intake` | Entry | Complete Reconcile before discussing a decision. |
| `formulate` | Reconcile complete | Build or revise all three Establish rows. Ask only an uncovered goal (G1). |
| `confirm` | All three established | Present the rationale, scope, exclusions, and landing approach together. Rejection → `formulate`. Acceptance → `$GATE_CONTROL gate-close --gate D --payload '<json>'` |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout D.

## Act

1. If `$CTX.gates.D.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE D`,
   and skip the loop.
2. Run `$GET_PAYLOAD --gate E`; pin `payloads.E` as `$E`. If E is missing,
   stop and report the missing required input.
3. Loop Modes (Signals as above) until `confirm` acceptance succeeds.

A missing required input or an unresolved conflict stops the gate until the user
provides direction.

## gate-close payload

```json
{
  "decision_rationale": "<chosen option and why>",
  "applies_to": "<scope coverage>",
  "excludes": "<explicit exclusions>",
  "execution_approach": "<landing approach at decision granularity>"
}
```

## Exit

`GATE_COMPLETE D` or `GATE_FAILED D reason=...`
