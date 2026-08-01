---
name: decision/gl-grill-runner
description: >-
  GL gate runner for decision. Goal-driven intent probe between Q and E;
  gate-close GL with lens-tagged exchanges. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# gl-grill-runner

Execute **GL — Intent Probe** (after Q, before E): reach two goals, then close.
Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user
direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.gates.Q.status` must be `closed` (from resolve-context)
- Dialogue semantics SSOT: this file’s **Cognitive map** (no separate gate file)
- Probe questions: apply `$SKILL_DIR/references/ask-protocol.md`

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-direction-ready` | Enough decision-domain operational/confirmation intent to choose a direction accurately at E. |
| `G-diagnosis-preflight` | Before direction choice: clear intent-layer mines that would overturn that choice (high-risk assumption / failure class / irreversible commitment). Active X dims are coverage handles only — not diagnosis prompts. |

`G-direction-ready` probes target operational/confirmation intent for direction
choice; they may cross dims freely. Active-X-dim coverage and demining shape are
not completion conditions for this goal.

`G-diagnosis-preflight` probes use active `$CTX.domain_constraints.x_dimensions`
as coverage handles (`lens` ids) only; phrase from locked Q + optional
`domain.dimension_profile` hints to match the Goals row — not as mini-X stems
or shallow X fills.

### Ask domain / bounds

- Anchor every probe to the locked Q problem + constraints.
- Decision-domain intent only. No implementation interview, WBS, or unbounded plan grilling.
- Freedom is which concrete question to ask — not any domain.

### Coverage

- `G-direction-ready`: further probes would not materially change the candidate
  direction set, or critical intent conflicts are already surfaced and recorded.
- `G-diagnosis-preflight`: each active X dim has a demining conclusion or a
  reasoned `na` the user understands. Unjustified all-`na` is not a pass.
- Evaluate using locked Q, this gate’s dialogue, and related G0 prior/assumptions.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `probe` | Either goal not met | Apply ask-protocol, then ask only the gap (G1). May pick next lens; order not fixed. |
| `summarize` | Both goals met | Restate key intents once; ask if ready for E (G8). |
| `close` | User confirms | `gate-close` with payload below. |

If the user rejects the summary: treat the denied point as a gap → `probe`.

### Pass criterion

Both goals met; Q still holds; G8 confirmed; ask-domain respected.
CLI green ≠ framework pass.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume (register `source` is `GL`).
- G9 / Q falsified → load RS; **do not** `gate-close` GL.
- Persist intents only via GL `gate-close` payload — do not dual-write exchanges to G0.

## Pipeline

**Entry:** Q closed. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as
`$CTX`. If `$CTX.gates.GL.status == stale`: follow
`$SKILL_DIR/references/stale-gate-update.md`, then return `GATE_COMPLETE GL`
(skip Act dialogue).

**Act:**

1. Apply `$CTX.domain_constraints` for all dialogue in this gate:
   - `objective` — session intent; frame the gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
   - `x_dimensions` / `domain.dimension_profile` — coverage handles and profile hints
2. Obtain locked Q via `$GATE_CONTROL get-payload` (or fields already on `$CTX`);
   do not start probes until Q payload is available.
3. Loop (Cognitive map):
   - Evaluate `G-direction-ready` / `G-diagnosis-preflight`.
   - If any gap → `probe` (side routes as above; then continue).
   - If both met → `summarize` → on confirm →
     `$GATE_CONTROL gate-close --gate GL --payload '<json>'` → break.
   - HARD: do not call `gate-close` until framework pass holds.

**Done:** Return `GATE_COMPLETE GL`.

**Stop:** Non-zero CLI, or coverage/confirm cannot be judged → stop and wait for
user direction.

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

On success:

```
GATE_COMPLETE GL
```

On failure:

```
GATE_FAILED GL reason=<brief description>
```
