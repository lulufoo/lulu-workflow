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
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/g0-parallel-registers.md`
- Identification hit this turn (gate contract § Identify)
- Active gate unchanged — resume after G0

## Pipeline

1. Gate contract § Execute — brief confirm with user
2. `$REGISTER_COMMIT` with append/update operations per gate contract
3. Pin `$CTX` from stdout
4. Return `G0_COMPLETE` — resume active gate dialogue

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
