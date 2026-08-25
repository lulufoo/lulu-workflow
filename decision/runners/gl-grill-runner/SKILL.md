---
name: decision/gl-grill-runner
description: Internal runner for the Decision GL gate.
meta-skill-version: 1.0.0
---

# gl-grill-runner

Surface decision-relevant user intent and critical uncertainties before direction
setting. Complete when the input is sufficient to enter E.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `GL`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.
- Probe questions: before the first probe in each GL entry, read
  `$SKILL_ROOT/shared/references/ask-protocol.md`; apply it to every probe.

## Intent

| ID | Must hold |
|----|-----------|
| `G-direction-ready` | Enough decision-domain operational/confirmation intent to choose a direction accurately at E. Further probes would not materially change the candidate direction set, or critical intent conflicts are already surfaced and recorded. |
| `G-diagnosis-preflight` | Before direction choice: clear intent-layer mines that would overturn that choice (high-risk assumption / failure class / irreversible commitment). Each active X dim has a demining conclusion or a reasoned `na` the user understands. Unjustified all-`na` is not a pass. |

`G-direction-ready` probes may cross dims freely. Active-X-dim coverage and
demining shape are not completion conditions for that row.

`G-diagnosis-preflight` uses active `$CTX.domain_constraints.x_dimensions` as
coverage handles (`lens` ids) only; phrase from locked Q + optional
`domain.dimension_profile` (`question` / `depth`) hints — not as mini-X stems
or shallow X fills.

Evaluate using locked Q, this gate’s dialogue, and related P prior/assumptions.
Both rows met + Q still holds + user confirmed ready for E + Ask domain
respected. CLI green ≠ framework pass.

## Ask domain

1. Anchor every probe to the locked Q problem + constraints.
2. Decision-domain intent only. No implementation interview, WBS, or unbounded
   plan grilling.
3. Freedom is which concrete question to ask — not any domain.

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `probe` | Either Intent row not met | Apply ask-protocol, then ask only the gap (G1). May pick next lens; order not fixed. |
| `summarize` | Both Intent rows met | Restate key intents once; ask if ready for E. |
| `close` | User confirms | `$GATE_CONTROL gate-close --gate GL --payload '<json>'` |

If the user rejects the summary: treat the denied point as a gap → `probe`.

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout GL.

## Act

1. If `$CTX.gates.GL.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE GL`,
   and skip the loop.
2. Obtain locked Q via `$GATE_CONTROL get-payload` (or fields already on `$CTX`);
   do not start probes until Q payload is available.
3. Loop Modes (Signals as above) until `close` succeeds. Do not call `gate-close`
   until both Intent rows hold, Q still holds, the user confirmed ready for E,
   and Ask domain was respected. On S1, register `source` is `GL`. Persist
   intents only via GL `gate-close` payload — do not dual-write exchanges to P.

## gate-close payload

```json
{
  "exchanges": [
    {
      "lens": "<active x_dimension_id>",
      "question": "<question>",
      "answer": "<user answer>",
      "na": false
    }
  ],
  "user_confirmed": true
}
```

- `lens` ∈ active `x_dimensions`; every active dim at least once (conclusion or `na: true`)
- Row rules and coverage: CLI (`dec_gate_control` / `--help`)
- `G-direction-ready` is framework-only (no extra payload slot)

## Exit

`GATE_COMPLETE GL` · `GATE_FAILED GL reason=<brief description>`
