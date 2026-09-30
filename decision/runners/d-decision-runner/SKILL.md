---
name: decision/d-decision-runner
description: Internal runner for the Decision D gate.
meta-skill-version: 1.0.0
---

# d-decision-runner

Define the selected direction's rationale, scope and exclusions, and landing
approach. Complete when the user confirms all three.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `D`, `$CTX.gl` present).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Reconcile

Check the selected E (rationale, scope, landing) against any settled Register write or gate-payload write. Conflict → revise E or load RS.

## Must hold

| ID | Must hold |
|----|-----------|
| `G-rationale` | The chosen direction, its E trade-offs, and why alternatives are excluded. Addresses every `concern` and `excluded` Prior, or states that none exist. |
| `G-scope` | What the decision covers and explicit exclusions. |
| `G-landing` | How this decision lands: in-scope must-do chunks, their roles, and dependencies (order or parallelism). Not a work breakdown, schedule, or staffing plan. |

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `intake` | Entry | Complete Reconcile before discussing a decision. |
| `formulate` | Reconcile complete | One question per unmet Must hold row (G1). |
| `confirm` | All three established | Present all three. Reject → `formulate`; accept → `$GATE_CONTROL gate-close --gate D --payload '<json>'`. |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout D.

## Act

1. If `$CTX.gates.D.status == stale`, follow `$DECISION_SKILL_DIR/references/rs-stale-gate-update.md`. Exactly one:
   - `$CTX.resume_gate` is `D` → continue at 2.
   - `$CTX.resume_gate` is not `D` → return `GATE_COMPLETE D` and skip the loop.
2. Run `$GET_PAYLOAD --gate E`; pin `payloads.E` as `$E`. If E is missing,
   stop and report the missing required input.
3. Loop Modes (Signals as above) until `confirm` acceptance succeeds.

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
