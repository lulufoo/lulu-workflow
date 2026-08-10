---
name: decision/q-problem-runner
description: >-
  Q gate runner for decision. Goal-driven problem clarification dialogue and
  gate-close Q with gate-payload write. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# q-problem-runner

Execute **Q — Problem Clarification**: reach two goals (problem + non-negotiable
constraints), then close. Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user
direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.gates.O.status` must be `closed` (from resolve-context)
- Dialogue semantics SSOT: this file’s **Cognitive map** (no separate gate file)
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
| `G-constraints` | What are the known, non-negotiable constraints? |

Constraints are **facts**, not decisions. Do not challenge or negotiate them away.

### Coverage

Evaluate both goals from the conversation so far, **including O prior** and
anything the user already stated before Q became active.

- **Covered:** user has stated an equivalent claim (or explicitly confirmed “no
  extra hard constraints” for an empty constraint set).
- **Gap:** goal not yet satisfied.
- If a goal is already covered: **do not** re-ask or split it into another
  confirmation round (G7). When **both** are covered on entry (typical after a
  rich O), go straight to **summarize** — never three confirmation rounds.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `probe` | Any goal has a gap | Apply ask-protocol, then ask only the gap (G1: one question per turn). Prefer one gap face per turn. |
| `summarize` | Both goals covered | Restate problem + constraints once; ask if correct. At most one waiting-for-confirm turn. |
| `close` | User confirms summarize | `gate-close` with payload below. |

If the user rejects the summary: treat the denied point as a gap → `probe`, then
re-evaluate.

Do **not** hard-code fixed question wording; phrase from goals +
`$CTX.domain_constraints`.

### Pass criterion

Problem statement is clear and agreed upon; constraints enumerated; user
confirmed the summary.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume goal evaluation.
- G9 hit → load RS runner → after return, resume goal evaluation.

## Pipeline

**Entry:** O closed. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as
`$CTX`. If `$CTX.gates.Q.status == stale`: follow
`$SKILL_DIR/references/stale-gate-update.md`, then return `GATE_COMPLETE Q`
(skip Act dialogue).

**Act:**

1. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
2. Loop (Cognitive map):
   - Evaluate `G-problem` / `G-constraints`.
   - If any gap → `probe` (side routes as above; then continue loop).
   - If both covered → `summarize` → on confirm →
     `$GATE_CONTROL gate-close --gate Q --payload '<json>'` → break.

**Done:** Return `GATE_COMPLETE Q`.

**Stop:** Non-zero CLI, or coverage/confirm cannot be judged → stop and wait for
user direction.

## gate-close payload

```json
{
  "problem_statement": "<agreed problem>",
  "constraints": "<enumerated constraints>"
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
