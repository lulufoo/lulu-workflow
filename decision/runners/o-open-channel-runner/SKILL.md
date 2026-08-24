---
name: decision/o-open-channel-runner
description: Internal runner for the Decision O gate.
meta-skill-version: 1.0.0
---

# o-open-channel-runner

Open the channel for existing User Prior or Assumption context. Complete when the
user is ready to enter Q; empty capture is valid.

## Prerequisites

<HARD-GATE>
1. Do NOT proceed until you have read `../../../_runtime.md`.
2. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- `$CTX.active_gate` must be `O` (from resolve-context)

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

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
| `listen` | User is sharing | Stay in channel; on G0 hit → G0 (see Side routes). |
| `confirm` | Ready to ask for Q | Ask whether they are ready to proceed to Q. |
| `close` | User confirms ready | `$GATE_CONTROL gate-close --gate O --payload '{"user_confirmed": true}'` |

User may go `invite` → `confirm` with zero prior content, or `listen` for several
turns before `confirm`.

Do **not** hard-code fixed invitation wording; phrase from goals +
`$CTX.domain_constraints`.

### Side routes

- G9 hit: load RS runner → after return, resume O dialogue.
- G0 hit: load G0 runner → `G0_COMPLETE` → resume O dialogue.

## Pipeline

**Entry:**

1. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.

**Act:** Loop the Dialogue modes (side routes as above) until `close` succeeds,
then Exit.

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE O` · `GATE_FAILED O reason=<brief description>`
