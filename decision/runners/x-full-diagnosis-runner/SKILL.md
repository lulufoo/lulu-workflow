---
name: decision/x-full-diagnosis-runner
description: Internal runner for the Decision X gate.
meta-skill-version: 1.0.0
---

# x-full-diagnosis-runner

Establish a complete, internally consistent execution diagnosis for the
settled decision. Complete when every active X dimension is covered and the
user confirms the packed draft.

## Context Binding

1. Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `X`).
2. Apply
  `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`, `dimension_profile`) to the dialogue.
3. Pin active dimensions from `$CTX.domain_constraints.x_dimensions`.
4. Run `$GET_PAYLOAD --preceding-of X`; pin returned payloads as settled
  preceding-gate evidence. Registers come from `$CTX`. Missing payloads are
   listed in `missing`; do not fail only because a specific prior gate is absent.

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout X.

## Dimension Diagnosis

For each active dimension:

1. **Target** — use `goal` to frame the intended result.
2. **Answer** — apply `question` to settled preceding-gate evidence and
  relevant global Register entries; form a restatable answer from existing
   evidence.
3. **Validate** — evaluate answer sufficiency against `completion`.
4. **Classify** — assign exactly one state:

| State | When |
|-------|------|
| Covered | A restatable answer to `question` satisfies `completion` and has no contradiction. |
| Gap | The answer is missing, not restatable, or fails `completion`. |
| Contradiction | The answer conflicts with another dimension or with a locked preceding-gate conclusion. Mark every involved dimension. |

## Session Loop

1. If `$CTX.gates.X.status == stale`, follow `$SKILL_DIR/references/rs-stale-gate-update.md`. Exactly one:
   - `$CTX.resume_gate` is `X` → continue at 2.
   - `$CTX.resume_gate` is not `X` → return `GATE_COMPLETE X` and skip 2–3.
2. Run Dimension Diagnosis for every active dimension.
3. Take one mode below. `probe` may repeat. Loop until `close` succeeds or
  `flag-gap` loads RS.

| Mode | When | Behavior |
|------|------|----------|
| `probe` | Any active dimension is a gap or contradiction | Pick only one (G1). Ask its `question`, or narrow it to the unmet part of `completion` or the contradiction; update the answer and rerun Dimension Diagnosis for that dimension. |
| `flag-gap` | All active dimensions Covered, no Contradiction, and `gap` is non-empty | Show the packed draft including the gap. Do not ask for confirm. Do not `gate-close`. Load RS. |
| `present` | All active dimensions Covered, no Contradiction, and `gap` is empty or `None` | Show the packed draft. Ask for one confirm. |
| `close` | User confirms the packed draft | `$GATE_CONTROL gate-close --gate X --payload '<json>'` (active-dimension fields only) |

## Output Contract

Submit only fields for active dimensions. Product domain: write user /
workflow / team mapping in `responsibility` and `stack`; write the
user-facing promise in `contract`.

```json
{
  "acceptance_criteria": "...",
  "gap": "None",
  "impact_surface": [
    {
      "responsibility": "...",
      "stack": "...",
      "area": "...",
      "change_type": "modify",
      "notes": "..."
    }
  ],
  "external_dependencies": [
    {
      "dependency": "...",
      "owner": "...",
      "required_state": "...",
      "contract": "...",
      "source": "...",
      "confirmation": "..."
    }
  ],
  "key_changes": "...",
  "critical_constraints": "...",
  "reversibility": "easy | partial | hard — why"
}
```

## Exit

`GATE_COMPLETE X` or `GATE_FAILED X reason=...`