---
name: decision/e-direction-runner
description: Internal runner for the Decision E gate.
meta-skill-version: 1.0.0
---

# e-direction-runner

Settle a direction from the locked problem and GL intent. Complete when the user
explicitly accepts a candidate direction.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `E`, `$CTX.gl` present).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.
- Align questions: apply `$SKILL_ROOT/shared/references/ask-protocol.md`

## Direction

| ID | Must hold |
|----|-----------|
| `G-settled-direction` | For the locked Q, a direction is settled: the user accepts a candidate as proposed, or accepts one after reshaping via an alternative; that settled direction is ready to record as `user_choice` and close E. |

Evaluate from locked Q, `$CTX.gl.exchanges`, this gate’s dialogue, and related
P prior/assumptions. Closable set: 2–3 directions, pros/cons, one recommended,
excluded listed or explicitly none. CLI green ≠ framework pass.

## Ask domain

1. Anchor to locked Q + closed GL intents (`$CTX.gl.exchanges`).
2. Decision-domain direction trade-offs only. No implementation interview, WBS,
   or unbounded plan grilling.
3. `define` gap asks only fill facts/preferences needed to build the candidate
   set — not a second GL demining pass.
4. Freedom is which concrete directions and trade-off faces — not any domain.

## Modes

Do not use `summarize`. `define`⇄`align` is the alignment loop: rejected set or
proposed alternative → `define`, then `align`.

| Mode | When | Behavior |
|------|------|----------|
| `define` | Direction not settled **and** no closable candidate set yet | Read `$CTX.gl.exchanges` in full first (prioritize `impact_surface`, `external_dependencies`, confirmation-related answers); surface conflicts. Build or revise the 2–3 set (and excluded). If material is insufficient, ask only the gap (G1). Do **not** apply the full ask-protocol. |
| `align` | Closable candidate set ready; direction not yet settled; GL intents consulted | Apply ask-protocol, then present the set and ask the user to accept a candidate or propose an alternative (G1). Lead with the recommended option. Presenting the options **is** this mode — no separate display-only turn. |
| `settle` | Direction settled (`user_choice` ready) | `$GATE_CONTROL gate-close --gate E --payload '<json>'`. Do **not** ask a separate close question after settle. |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout E.

## Act

1. If `$CTX.gates.E.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE E`,
   and skip the loop.
2. Confirm `$CTX.gl` is present. Loop Modes (Signals as above) until `settle`
   succeeds. Do not call `gate-close` until `G-settled-direction` holds and Ask
   domain was respected.

## gate-close payload

```json
{
  "directions": [
    {
      "name": "Option A",
      "approach": "...",
      "pros": "...",
      "cons": "...",
      "recommended": true
    }
  ],
  "excluded": [{"name": "...", "reason": "..."}],
  "user_choice": "<chosen direction>"
}
```

Requires **2–3** directions in `directions` (CLI). Row rules: CLI
(`dec_gate_control` / `--help`).

## Exit

`GATE_COMPLETE E` · `GATE_FAILED E reason=<brief description>`
