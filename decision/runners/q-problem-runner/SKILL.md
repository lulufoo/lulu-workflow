---
name: decision/q-problem-runner
description: Internal runner for the Decision Q gate.
meta-skill-version: 1.0.0
---

# q-problem-runner

Write and confirm the problem statement. Complete when the user confirms it.
Hard constraints are already on `C#` via G0; do not collect them here.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user
direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
1. Do NOT proceed until you have read `../../../_runtime.md`.
2. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.active_gate` must be `Q` (from resolve-context)
- Probe questions: apply `$SKILL_ROOT/shared/references/ask-protocol.md`

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-problem` | What triggered this decision? What problem are we solving? |

Do not re-collect hard constraints. New facts / unverified claims / judgments
go to G0 as `C#` / `A#` / `P#`.

### Coverage

Evaluate `G-problem` from the conversation so far, **including O prior**.

- **Covered:** user has stated an equivalent problem claim.
- **Gap:** problem not yet satisfied.
- If already covered on entry: go straight to **summarize** (G7).

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `probe` | `G-problem` has a gap | Apply ask-protocol; one question per turn (G1). |
| `summarize` | `G-problem` covered | Restate the problem once; ask if correct. |
| `close` | User confirms summarize | `gate-close` with payload below. |

If the user rejects the summary: treat the denied point as a gap → `probe`.

Do **not** hard-code fixed question wording; phrase from the goal +
`$CTX.domain_constraints`.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume goal evaluation.
- G9 hit → load RS runner → after return, resume goal evaluation.

## Pipeline

**Entry:**

1. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
2. If `$CTX.gates.Q.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md`, return `GATE_COMPLETE Q`,
   and skip Act.

**Act:**

1. Loop (Cognitive map):
   - Evaluate `G-problem`.
   - If gap → `probe` (side routes as above; then continue loop).
   - If covered → `summarize` → on confirm →
     `$GATE_CONTROL gate-close --gate Q --payload '<json>'` → break.

**Done:** Return `GATE_COMPLETE Q`.

**Stop:** Non-zero CLI, or coverage/confirm cannot be judged → stop and wait for
user direction.

## gate-close payload

```json
{
  "problem_statement": "<agreed problem>"
}
```

## Exit

On success:

```
GATE_COMPLETE Q
```

On failure:

```
GATE_FAILED Q reason=<brief description>
```
