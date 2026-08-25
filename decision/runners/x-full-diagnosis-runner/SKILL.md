---
name: decision/x-full-diagnosis-runner
description: Internal runner for the Decision X gate.
meta-skill-version: 1.0.0
---

# x-full-diagnosis-runner

Diagnose the pinned X dimensions against each `dimension_profile.goal`. Complete when the user confirms the packed draft of all active dimensions.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |

Subcommand contracts: module docstring / `--help`.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `X`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`, `domain.instruction`, `x_dimensions`, `dimension_profile`) to the dialogue.

## Dimensions

Diagnose only `$CTX.domain_constraints.x_dimensions`. Read each row's `question`, `depth`, and `goal` from `$CTX.domain_constraints.domain.dimension_profile[<dimension>]`. A missing or incomplete profile → stop. `depth` is the ceiling.

## Coverage

Evaluate each active dimension from this session, `$CTX.gl`, `$E`, `$D`, and related P priors.

| State | When |
|-------|------|
| Covered | A restatable conclusion meets this dimension's `goal` and stays within `depth`. |
| Gap | Conclusion missing, not restatable, or fails `goal`. |
| Contradiction | The conclusion conflicts with another dimension or with locked E/D. Mark every involved dimension. |

Do not re-ask a covered dimension. If the user names a dimension, treat it as unresolved.

## Modes

`probe` may repeat. One gap or contradiction per turn.

| Mode | When | Behavior |
|------|------|----------|
| `probe` | Any active dimension is a gap or contradiction | Ask only that one (G1). Use `question` as the default stem, or a more specific gap/contradiction question. |
| `flag-gap` | All active dimensions Covered, no Contradiction, and `gap` is non-empty | Show the packed draft including the gap. Do not ask for confirm. Do not `gate-close`. Load RS. |
| `present` | All active dimensions Covered, no Contradiction, and `gap` is empty or `None` | Show the packed draft. Ask for one confirm. |
| `close` | User confirms the packed draft | `$GATE_CONTROL gate-close --gate X --payload '<json>'` (active-dimension fields only) |

If the user rejects the `present` draft, treat the denied point as that dimension's gap or contradiction → `probe` only that dimension.

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout X.

## Act

1. If `$CTX.gates.X.status == stale`, follow `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE X`, and skip the loop.
2. Run `$GET_PAYLOAD --gates E,D`; pin `payloads.E` as `$E` and `payloads.D` as `$D`. If either is missing, stop and report the missing required input.
3. Loop Modes (Signals as above) until `close` succeeds or `flag-gap` loads RS.

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
