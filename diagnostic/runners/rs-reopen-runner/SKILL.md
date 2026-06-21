---
name: diagnostic/rs-reopen-runner
description: >-
  RS subroutine for diagnostic. Dialogue and register proposals before atomic
  rs-commit. Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# rs-reopen-runner

Execute **RS — Reopen State Handler**. Proposes register relabeling; persists via `$RS_COMMIT`.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/rs-reopen-state-handler.md`
- Reopen gate `G` identified (Q / E / D / X) — from trigger context or user

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`; baseline before proposals (not conversation memory)
2. Confirm reopen gate `G` with user (G8)
3. Propose 3-state labeling for all register entries per gate contract Step 3; user confirms (G8)
4. `$RS_COMMIT` with `--gate <G>` and `--operations '<json array>'` (use `[]` if no register changes)
5. Pin `$CTX` from stdout (`reenter`, `gates`, `registers`, `domain_constraints`)
6. Return `RS_COMPLETE reenter=<G>` — load gate `G` runner via kernel § Gate routing

## `--operations` format

```json
[
  {"id": "P2", "action": "set_state", "state": "pending"},
  {"id": "A3", "action": "set_state", "state": "verified"},
  {"id": "A4", "action": "delete"}
]
```

- `set_state`: `pending` | `verified` (maps to `[待验证]` / `[已验证]`)
- `delete` or `set_state: invalidated` → remove entry (`[失效]`)

## Exit

`RS_COMPLETE reenter=Q` (or E / D / X)
