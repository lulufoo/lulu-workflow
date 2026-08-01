---
name: decision/o-open-channel-runner
description: >-
  O gate runner for decision. LoopA entry: optional prior dump, confirm ready
  for Q, gate-close O. Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# o-open-channel-runner

Execute **O — Open Channel** (LoopA entry): invite optional prior / assumption
capture, then confirm readiness for Q. Mechanical persistence via `$GATE_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user
direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.active_gate` must be `O` (from resolve-context)
- Dialogue semantics SSOT: this file’s **Cognitive map** (no separate gate file)

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --stage "<stage>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`.

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-invite` | Open channel: invite the user to share existing knowledge (direction preferences, concerns, ruled-out options, etc.). Completeness is not required; they may add more later. |
| `G-ready` | User confirms they are ready to proceed to Q. |

### Coverage / bounds

- **Prior dump is optional.** Empty prior / assumption registers are allowed. Do
  **not** block close because little or nothing was dumped.
- **Parent context docs** were already loaded at Active bind — do **not** reload
  them in O.
- Dialogue in this gate **does not count** toward Q’s question quota.
- O does **not** clarify problem statement or non-negotiable constraints — that
  is Q’s job.
- If an equivalent invite already happened in this session before O dialogue
  started, treat `G-invite` as satisfied; do not stack redundant invites.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `invite` | `G-invite` not yet satisfied | Issue the open-channel invite (intent above; do not hard-code fixed wording). |
| `listen` | User is sharing | Stay in channel; on identification hit → G0 (see Side routes). |
| `confirm` | Ready to ask for Q | Ask whether they are ready to proceed to Q. |
| `close` | User confirms ready | `gate-close` with payload below. |

User may go `invite` → `confirm` with zero prior content, or `listen` for several
turns before `confirm`.

Do **not** hard-code fixed invitation wording; phrase from goals +
`$CTX.domain_constraints`.

### Pass criterion

User confirms they are ready to proceed to Q. Prior dump is optional —
empty registers are allowed.

### Side routes

- Identification hit → load G0 runner → `G0_COMPLETE` → resume O dialogue.
- G9 hit → load RS runner → after return, resume O dialogue.

## Pipeline

**Entry:** `$CTX.active_gate` is `O`. Run `$GATE_CONTROL resolve-context`; pin
stdout JSON as `$CTX`. (No stale branch for O.)

**Act:**

1. Apply `$CTX.domain_constraints` for all dialogue in this gate:
   - `objective` — session intent; frame the gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
2. Cognitive map loop:
   - Ensure `G-invite` (invite if needed).
   - `listen` as the user shares (side routes as above).
   - `confirm` ready for Q → on confirm →
     `$GATE_CONTROL gate-close --gate O --payload '{"user_confirmed": true}'`
     → break.

**Done:** Return `GATE_COMPLETE O`.

**Stop:** Non-zero CLI, or readiness cannot be judged → stop and wait for user
direction.

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

On success:

```
GATE_COMPLETE O
```

On failure:

```
GATE_FAILED O reason=<brief description>
```
