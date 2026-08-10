---
name: decision/d-decision-runner
description: Internal runner for the Decision D gate.
meta-skill-version: 1.0.0
---

# d-decision-runner

Define the selected direction's rationale, scope and exclusions, and landing
approach. Complete when the user confirms all three.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
1. Do NOT proceed until you have read `../../../_runtime.md`.
2. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
</HARD-GATE>

- `$CTX.active_gate` must be `D` (from resolve-context)
- `$CTX.gl` must be present

## Cognitive map

### Inputs to reconcile

Before D dialogue:

1. Read `$CTX.registers.prior` and `$CTX.gl.exchanges` in full.
2. Compare GL confirmation and operational intents with the chosen E direction
   and intended scope.
3. Compare every Prior with the chosen E direction and intended scope.
4. Surface and resolve every GL or Prior conflict explicitly in the Decision
   Rationale.

### Goals

| ID | Must establish |
|----|----------------|
| `G-rationale` | The chosen direction, its E trade-offs, and why alternatives are excluded. |
| `G-scope` | What the decision covers and explicit exclusions. |
| `G-landing` | The in-scope must-do chunks, their roles, dependencies, and order or parallelism. This is decision-level landing, not a work breakdown, schedule, or staffing plan. |

### Pass criterion

All three goals are established; exclusions are explicit; the rationale
references E trade-offs, reconciles GL intents, and addresses every `concern`
and `excluded` Prior (or states that no such Prior exists); the user confirms.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `reconcile` | Entry | Complete Inputs to reconcile before discussing a decision. |
| `formulate` | Inputs reconciled | Build or revise all three goals. Ask only an uncovered goal (G1/G7). |
| `confirm` | All goals are complete | Present the rationale, scope, exclusions, and landing approach together. User rejection returns to `formulate`; acceptance closes D. |

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume the current
  mode.
- G9 hit → load RS runner.

## Pipeline

**Entry:**

1. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
2. If `$CTX.gates.D.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE D`,
   and skip Act.

**Act:**

1. Complete Cognitive map **Inputs to reconcile**.
2. Loop through `reconcile` → `formulate` → `confirm`. On acceptance, run
   `$GATE_CONTROL gate-close --gate D --payload '<json>'`.

**Done:** Return `GATE_COMPLETE D`.

**Stop:** Non-zero CLI, a missing required input, or an unresolved conflict
stops the gate until the user provides direction.

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
