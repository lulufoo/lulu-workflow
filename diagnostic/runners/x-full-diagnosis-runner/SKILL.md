---
name: diagnostic/x-full-diagnosis-runner
description: >-
  X gate runner for diagnostic. Full diagnosis dialogue and gate-close X with
  execution analysis sections. Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# x-full-diagnosis-runner

Execute **X — Full Diagnosis** (all five dimensions in one gate-close). Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/x-full-diagnosis.md`
- `$CTX.gates.D.status` must be `closed`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`; read `$CTX.domain_constraints.x_dimensions` for active dimensions only
2. Execute active X dimensions one at a time (G1/G7/G8 per dimension); skip dimensions not in `x_dimensions`
3. G0 assumptions per parent § Parallel Registers
4. `$GATE_CONTROL gate-close --gate X --payload '<json>'` (only fields for active dimensions required)
5. Return `GATE_COMPLETE X`

Active dimension keys: `acceptance_criteria` · `impact_surface` · `external_dependencies` · `implementation_sketch` · `gap_check`

## gate-close payload

```json
{
  "acceptance_criteria": "...",
  "gap": "None",
  "impact_surface": [
    {"layer": "...", "area": "...", "change_type": "modify", "notes": "..."}
  ],
  "external_dependencies": [
    {"dependency": "...", "contract": "...", "source": "...", "confirmation": "..."}
  ],
  "key_changes": "...",
  "critical_constraints": "...",
  "reversibility": "easy | partial | hard — why"
}
```

## Exit

`GATE_COMPLETE X` or `GATE_FAILED X reason=...`
