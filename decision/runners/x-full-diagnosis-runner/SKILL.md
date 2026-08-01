---
name: decision/x-full-diagnosis-runner
description: >-
  X gate runner for decision. Full diagnosis dialogue and gate-close X with
  execution analysis sections. Invoked by decision/SKILL.md.
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
2. If `$CTX.gates.X.status == stale`: follow `$SKILL_DIR/references/stale-gate-update.md` then return `GATE_COMPLETE X`
3. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
   - `domain.dimension_profile` — per-dimension `{question, depth}`; applied in step 4
4. Execute active X dimensions one at a time (G1/G7 per dimension; user confirms each dim); skip dimensions not in `x_dimensions`. For each active dimension, read `domain.dimension_profile[dimension]`: use its `question` as the Core question when present (else gate table default); apply its `depth` as the depth ceiling when present (else gate Granularity baseline); before asking confirm, self-check the draft against that ceiling.
5. During dialogue: on identification hit → G0 runner → `G0_COMPLETE` → continue; on G9 hit → RS runner
6. `$GATE_CONTROL gate-close --gate X --payload '<json>'` (only fields for active dimensions required)
7. Return `GATE_COMPLETE X`

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
