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
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/d-decision-scope.md`
- `$CTX.active_gate` must be `D` (from resolve-context)
- `$CTX.gates.E.status` must be `closed`

## Pipeline

**Entry:**

1. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
3. If `$CTX.gates.D.status == stale`, follow
   `$SKILL_DIR/references/stale-gate-update.md`, return `GATE_COMPLETE D`,
   and skip Act.

**Act:**

1. Gate contract § Before entering — consult `$CTX.registers.prior` and
   `$CTX.gl`; do not start D dialogue until complete.
2. Execute D gate (G1/G7; on identification hit → G0 runner →
   `G0_COMPLETE` → continue; on G9 hit → RS runner).
3. `$GATE_CONTROL gate-close --gate D --payload '<json>'`.

**Done:** Return `GATE_COMPLETE D`.

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
