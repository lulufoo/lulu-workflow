---
name: decision/x-full-diagnosis-runner
description: Internal runner for the Decision X gate.
meta-skill-version: 1.0.0
---

# x-full-diagnosis-runner

Diagnose the active X dimensions at decision granularity. Complete when the user
confirms each active dimension's result.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/x-full-diagnosis.md`
- `$CTX.active_gate` must be `X` (from resolve-context)
- `$CTX.gates.D.status` must be `closed`

## Pipeline

**Entry:**

1. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
3. If `$CTX.gates.X.status == stale`, follow
   `$SKILL_DIR/references/stale-gate-update.md`, return `GATE_COMPLETE X`,
   and skip Act.

**Act:**

1. Execute active X dimensions one at a time (G1/G7 per dimension; user
   confirms each dim); skip dimensions not in `x_dimensions`. For each active
   dimension, read `domain.dimension_profile[dimension]`: use its `question` as
   the Core question when present (else gate table default); apply its `depth` as
   the depth ceiling when present (else gate Granularity baseline); before asking
   confirm, self-check the draft against that ceiling.
2. During dialogue: on identification hit → G0 runner → `G0_COMPLETE` →
   continue; on G9 hit → RS runner.
3. `$GATE_CONTROL gate-close --gate X --payload '<json>'` (only fields for
   active dimensions required).

**Done:** Return `GATE_COMPLETE X`.

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
