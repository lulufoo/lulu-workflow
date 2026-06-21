---
name: diagnostic/d-decision-runner
description: >-
  D gate runner for diagnostic. Decision rationale, scope, and execution
  approach dialogue with gate-close D. Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# d-decision-runner

Execute **D — Decision & Scope**. Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/d-decision-scope.md`
- `$CTX.gates.E.status` must be `closed`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Review User Prior from `$CTX.registers` before dialogue
3. Execute D gate (G1/G7/G8; G0 per parent § Parallel Registers)
4. `$GATE_CONTROL gate-close --gate D --payload '<json>'`
5. Return `GATE_COMPLETE D`

## gate-close payload

```json
{
  "decision_rationale": "<chosen option and why>",
  "applies_to": "<scope coverage>",
  "excludes": "<explicit exclusions>",
  "execution_approach": "<sequencing preferences>"
}
```

## Exit

`GATE_COMPLETE D` or `GATE_FAILED D reason=...`
