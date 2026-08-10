---
name: decision/g0-parallel-registers-runner
description: Internal runner for the Decision G0 global gate.
meta-skill-version: 1.0.0
---

# g0-parallel-registers-runner

Capture newly identified User Prior and Assumptions without changing the active
gate. Complete when the entries are committed and the interrupted gate resumes.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
1. Do NOT proceed until you have read `../../../_runtime.md`.
2. Confirm an identification hit occurred this turn.
3. Use the interrupted flow's `$CTX` to confirm one of:
   - Session is InProgress.
   - Session is Frozen after reopen, and G0 interrupts RS before `$RS_COMMIT`.
</HARD-GATE>

- Active gate unchanged — resume after G0

## Cognitive map

### Classification

| Signal in dialogue | Log | Also log |
|--------------------|-----|----------|
| Judgment about the problem or solution | Prior · `judgment` | — |
| Preference between options or approaches | Prior · `preference` | — |
| Worry, risk, or blocker | Prior · `concern` | — |
| Ruled-out option | Prior · `excluded` | — |
| Explicit or implicit unverified premise | Assumption | — |
| Prior resting on an unverified premise | Prior (matching kind) | Assumption for the premise |

Recognize Assumptions as they surface; do not defer them to R.

### Bounds

- G0 runs alongside the interrupted gate, does not change `active_gate`, and
  does not call `gate-close`.
- Confirm the proposed entries briefly with the user before persistence.
- Persist only through `$REGISTER_COMMIT`; do not hand-edit registers or chain
  register commands.
- Reading or organizing Prior belongs to D or R. Bulk Assumption updates belong
  to R; RS owns register batches during realignment.
- The Frozen exception resumes the interrupted RS confirmation; do not resume a
  spine gate.

## Pipeline

**Entry:**

1. Classify every identification hit with the Cognitive map.

**Act:**

1. Briefly confirm the proposed Prior and Assumption entries with the user.
2. Run `$REGISTER_COMMIT` with the required append/update operations.
3. Pin `$CTX` from stdout.

**Done:** Return `G0_COMPLETE` and resume the interrupted gate dialogue.

**Stop:** Non-zero command → stop, report error, wait for user direction.

## register-commit

One or more operations per `$REGISTER_COMMIT` invocation. Subcommand contract: `$REGISTER_CONTROL --help` (`register-commit`).

Append example:

```json
[
  {"action": "append", "kind": "prior", "payload": {"kind": "concern", "text": "..."}},
  {"action": "append", "kind": "assumption", "payload": {"text": "..."}}
]
```

## Exit

`G0_COMPLETE` or `G0_FAILED reason=...`
