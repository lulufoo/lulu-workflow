---
name: diagnostic/g0-parallel-registers-runner
description: >-
  G0 global parallel gate for diagnostic. Captures User Prior and Assumption
  entries via register-commit when identification hits during spine or RS
  gate dialogue. Invoked by diagnostic/SKILL.md Gate routing.
meta-skill-version: 1.0.0
---

# g0-parallel-registers-runner

Execute **G0 — Parallel Registers** (global · parallel). Mechanical persistence via `$REGISTER_COMMIT`.

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
