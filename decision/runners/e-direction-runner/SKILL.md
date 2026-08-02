---
name: decision/e-direction-runner
description: >-
  E gate runner for decision. Goal-driven direction set and user choice after
  GL; gate-close E with directions payload. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# e-direction-runner

Execute **E — Direction Exploration** (after GL, before D): reach two goals
(direction set + user choice), then close. Mechanical persistence via
`$GATE_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user
direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.gates.GL.status` must be `closed` (from resolve-context)
- `$CTX.gl` must be present when GL is closed
- Dialogue semantics SSOT: this file’s **Cognitive map** (no separate gate file)
- Choose questions: apply `$SKILL_DIR/references/ask-protocol.md`

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-direction-set` | A closable package of **2–3** directions: each with approach, pros, cons; exactly one recommended; GL intents consulted; excluded listed or explicitly none. |
| `G-choice` | User has chosen a direction (or proposed an alternative that was folded into the set, then chosen). |

### Ask domain / bounds

- Anchor to locked Q + closed GL intents (`$CTX.gl.exchanges`).
- Decision-domain direction trade-offs only. No implementation interview, WBS, or
  unbounded plan grilling.
- `compose` gap asks only fill facts/preferences needed to build the set — not a
  second GL demining pass.
- Freedom is which concrete directions and trade-off faces — not any domain.

### Coverage

Evaluate both goals from locked Q, `$CTX.gl.exchanges`, this gate’s dialogue, and
related G0 prior/assumptions.

- **Before proposing:** read `$CTX.gl.exchanges` in full; prioritize
  `impact_surface`, `external_dependencies`, and confirmation-related answers;
  surface conflicts with candidate directions. Do not start `choose` until GL
  intents have been consulted.
- `G-direction-set`: package shape matches close payload (2–3 directions; pros/
  cons present; one recommended; excluded handled). Material conflicts with GL
  are surfaced.
- `G-choice`: explicit selection ready for `user_choice`. No separate close-
  confirmation round after the choice.
- If the set is rejected or an alternative is proposed: treat as set gap →
  `compose`, then re-enter `choose`.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `compose` | `G-direction-set` not met | Build or revise the 2–3 package (and excluded). If material is insufficient, ask only the gap (G1/G7). Do **not** apply ask-protocol. |
| `choose` | Set ready; choice not yet made | Apply ask-protocol, then present the package and ask the user to choose or propose an alternative (G1). Lead with the recommended option. Presenting the options **is** this mode — no separate display-only turn. |
| `close` | User has chosen | `gate-close` with payload below. Do **not** ask a separate close question after the choice. |

Do **not** use `summarize`. Do **not** hard-code fixed wording; phrase from
goals + `$CTX.domain_constraints`.

### Pass criterion

≥2 directions evaluated with explicit pros/cons; user has chosen (or indicated
a preference recorded as `user_choice`); ask-domain respected; GL intents were
consulted. CLI green ≠ framework pass.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume goal evaluation.
- G9 hit → load RS runner → after return, resume goal evaluation.

## Pipeline

**Entry:** GL closed. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as
`$CTX`. If `$CTX.gates.E.status == stale`: follow
`$SKILL_DIR/references/stale-gate-update.md`, then return `GATE_COMPLETE E`
(skip Act dialogue).

**Act:**

1. Apply `$CTX.domain_constraints` for all dialogue in this gate:
   - `objective` — session intent; frame the gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
2. Confirm `$CTX.gl` is present; consult `$CTX.gl.exchanges` before proposing
   directions (Coverage).
3. Loop (Cognitive map):
   - Evaluate `G-direction-set` / `G-choice`.
   - If set has a gap → `compose` (side routes as above; then continue).
   - If set ready and choice missing → `choose`.
   - If choice made →
     `$GATE_CONTROL gate-close --gate E --payload '<json>'` → break.
   - HARD: do not call `gate-close` until framework pass holds.

**Done:** Return `GATE_COMPLETE E`.

**Stop:** Non-zero CLI, or coverage/choice cannot be judged → stop and wait for
user direction.

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

On success:

```
GATE_COMPLETE E
```

On failure:

```
GATE_FAILED E reason=<brief description>
```
