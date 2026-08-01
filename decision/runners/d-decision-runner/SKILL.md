---
name: decision/d-decision-runner
description: >-
  D gate runner for decision. Decision rationale, scope, and execution
  approach dialogue with gate-close D. Invoked by decision/SKILL.md.
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
2. If `$CTX.gates.D.status == stale`: follow `$SKILL_DIR/references/stale-gate-update.md` then return `GATE_COMPLETE D`
3. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
4. Gate contract § Before entering — consult `$CTX.registers.prior` and `$CTX.gl`; do not start D dialogue until complete
5. Execute D gate (G1/G7; on identification hit → G0 runner → `G0_COMPLETE` → continue; on G9 hit → RS runner)
6. `$GATE_CONTROL gate-close --gate D --payload '<json>'`
7. Return `GATE_COMPLETE D`

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
