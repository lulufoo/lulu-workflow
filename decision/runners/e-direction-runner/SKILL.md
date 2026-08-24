---
name: decision/e-direction-runner
description: Internal runner for the Decision E gate.
meta-skill-version: 1.0.0
---

# e-direction-runner

Settle a direction from the locked problem and GL intent. Complete when the user
explicitly accepts a candidate direction.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `E`, `$CTX.gl` present).
- Align questions: apply `$SKILL_ROOT/shared/references/ask-protocol.md`

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-settled-direction` | For the locked Q, a direction is settled: the user accepts a candidate as proposed, or accepts one after reshaping via an alternative; that settled direction is ready to record as `user_choice` and close E. |

### Ask domain / bounds

- Anchor to locked Q + closed GL intents (`$CTX.gl.exchanges`).
- Decision-domain direction trade-offs only. No implementation interview, WBS, or
  unbounded plan grilling.
- `define` gap asks only fill facts/preferences needed to build the candidate
  set — not a second GL demining pass.
- Freedom is which concrete directions and trade-off faces — not any domain.

### Coverage

Evaluate `G-settled-direction` from locked Q, `$CTX.gl.exchanges`, this gate’s
dialogue, and related G0 prior/assumptions.

- **Before proposing:** read `$CTX.gl.exchanges` in full; prioritize
  `impact_surface`, `external_dependencies`, and confirmation-related answers;
  surface conflicts with candidate directions. Do not start `align` until GL
  intents have been consulted.
- **Candidate-set readiness (means, not a Goal):** set shape matches close
  payload (2–3 directions; pros/cons present; one recommended; excluded listed
  or explicitly none). Material conflicts with GL are surfaced.
- **Settlement:** explicit accept (including after reshape) ready for
  `user_choice`. No separate close-confirmation round after settle.
- **Alignment loop:** `define`⇄`align` is the alignment loop. If the set is
  rejected or an alternative is proposed: back to `define`, then `align`.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `define` | Direction not settled **and** no closable candidate set yet | Build or revise the 2–3 set (and excluded). If material is insufficient, ask only the gap (G1/G7). Do **not** apply ask-protocol. |
| `align` | Closable candidate set ready; direction not yet settled | Apply ask-protocol, then present the set and ask the user to accept a candidate or propose an alternative (G1). Lead with the recommended option. Presenting the options **is** this mode — no separate display-only turn. |
| `settle` | Direction settled (`user_choice` ready) | `$GATE_CONTROL gate-close --gate E --payload '<json>'`. Do **not** ask a separate close question after settle. |

Do **not** use `summarize`.

### Pass criterion

≥2 directions evaluated with explicit pros/cons; direction settled (recorded as
`user_choice`); ask-domain respected; GL intents were consulted. CLI green ≠
framework pass.

### Side routes

- G9 hit: load RS runner → after return, resume goal evaluation.
- G0 hit: load G0 runner → `G0_COMPLETE` → resume goal evaluation.

## Pipeline

**Entry:**

1. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
2. If `$CTX.gates.E.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE E`,
   and skip Act.
3. Confirm `$CTX.gl` is present; consult `$CTX.gl.exchanges` before proposing
   directions (Coverage).

**Act:** Loop the Dialogue modes (side routes as above) until `settle` succeeds,
then Exit. Do not call `gate-close` until the Pass criterion holds.

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
