---
name: decision/e-direction-runner
description: >-
  E gate runner for decision. Goal-driven settled direction after GL;
  gate-close E with directions payload. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# e-direction-runner

Execute **E — Direction Exploration** (after GL, before D): settle a
direction (`G-settled-direction`), then close. Mechanical persistence via
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
| `settle` | Direction settled (`user_choice` ready) | `gate-close` with payload below. Do **not** ask a separate close question after settle. |

Do **not** use `summarize`. Do **not** hard-code fixed wording; phrase from
goals + `$CTX.domain_constraints`.

### Pass criterion

≥2 directions evaluated with explicit pros/cons; direction settled (recorded as
`user_choice`); ask-domain respected; GL intents were consulted. CLI green ≠
framework pass.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume goal evaluation.
- G9 hit → load RS runner → after return, resume goal evaluation.

## Pipeline

**Entry:**

1. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
2. Confirm `$CTX.active_gate` is `E`; otherwise do not proceed.
3. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
4. If `$CTX.gates.E.status == stale`, follow
   `$SKILL_DIR/references/stale-gate-update.md`, return `GATE_COMPLETE E`,
   and skip Act.

**Act:**

1. Confirm `$CTX.gl` is present; consult `$CTX.gl.exchanges` before proposing
   directions (Coverage).
2. Loop (Cognitive map):
   - Evaluate `G-settled-direction`.
   - If candidate set not ready → `define` (side routes as above; then
     continue).
   - If set ready and direction not settled → `align`.
   - If direction settled →
     `$GATE_CONTROL gate-close --gate E --payload '<json>'` → break.
   - HARD: do not call `gate-close` until framework pass holds.

**Done:** Return `GATE_COMPLETE E`.

**Stop:** Non-zero CLI, or coverage/settlement cannot be judged → stop and wait
for user direction.

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
