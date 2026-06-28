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
2. Apply Role from `$CTX.domain_constraints` if present
3. Gate contract § Before entering — do not start D dialogue until complete
4. Execute D gate (G1/G7/G8; on identification hit → G0 runner → `G0_COMPLETE` → continue)
5. `$GATE_CONTROL gate-close --gate D --payload '<json>'`
6. Return `GATE_COMPLETE D`

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
