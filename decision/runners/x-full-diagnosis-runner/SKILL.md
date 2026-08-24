---
name: decision/x-full-diagnosis-runner
description: Internal runner for the Decision X gate.
meta-skill-version: 1.0.0
---

# x-full-diagnosis-runner

Diagnose active X dimensions against each `dimension_profile.goal`. Complete
when the user confirms the packed draft of all active dimensions.

## Prerequisites

<HARD-GATE>
1. Do NOT proceed until you have read `../../../_runtime.md`.
2. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
</HARD-GATE>

- `$CTX.active_gate` must be `X` (from resolve-context)

## Cognitive map

### Active-dimension rules

- Execute only `$CTX.domain_constraints.x_dimensions`; do not infer dimensions
  from holder prose.
- Read each active dimension's `question`, `depth`, and `goal` from
  `$CTX.domain_constraints.domain.dimension_profile[<dimension>]`. No table
  fallback.
- A missing or incomplete profile on an active dimension → stop; do not open
  dialogue.
- `depth` is the ceiling. Self-check the draft against it before showing it.

### Coverage

Evaluate each active dimension from this session, `$CTX.gl`, `$E`, `$D`, and
related G0 priors.

| State | When |
|-------|------|
| Covered | A restatable conclusion meets this dimension's `goal` and stays within `depth`. |
| Gap | Conclusion missing, not restatable, or fails `goal`. |
| Contradiction | The conclusion conflicts with another dimension or with locked E/D. Mark every involved dimension. |

Do not re-ask a covered dimension. If the user names a dimension, treat it as
unresolved.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `probe` | Any active dimension is a gap or contradiction | Ask only that one (G1). Use `question` as the default stem, or a more specific gap/contradiction question. |
| `flag-gap` | All active dimensions Covered, no Contradiction, and `gap` is non-empty | Show the packed draft including the gap. Do not ask for confirm. Do not `gate-close`. Load RS. |
| `present` | All active dimensions Covered, no Contradiction, and `gap` is empty or `None` | Show the packed draft. Ask for one confirm. |
| `close` | User confirms the packed draft | `gate-close` with payload below. |

`probe` may repeat. One gap or contradiction per turn.

If the user rejects the `present` draft, treat the denied point as that
dimension's gap or contradiction → `probe` only that dimension.

### Output rule

Gap Check does not create a separate document section. Record its result in the
`gap` field for the decision document's Acceptance Criteria → Gap (if any).

### Side routes

- G0 hit → load G0 runner immediately → `G0_COMPLETE` → resume the
  current mode (`probe` or `present`).
- G9 hit → load RS runner.
- Non-empty `gap` after all dimensions are Covered → `flag-gap`.

## Pipeline

**Entry:**

1. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`, `x_dimensions`, `dimension_profile`) to the dialogue.
2. If `$CTX.gates.X.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE X`,
   and skip Act.
3. Run `$GET_PAYLOAD --gates E,D`; pin `payloads.E` as `$E` and `payloads.D` as
   `$D`. If either is missing, stop and report the missing required input.

**Act:**

1. Loop (Cognitive map):
   - Evaluate each active dimension.
   - If any gap or contradiction → `probe`.
   - If all Covered and `gap` is non-empty → `flag-gap` → break.
   - If all Covered and `gap` is empty or `None` → `present` → on confirm →
     `$GATE_CONTROL gate-close --gate X --payload '<json>'` (only
     active-dimension fields are required) → break.

**Done:** Return `GATE_COMPLETE X`.

**Stop:** An unconfirmed packed draft, a missing required payload, or a gap
that requires realignment stops X.

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
