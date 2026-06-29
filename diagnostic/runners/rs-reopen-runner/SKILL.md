---
name: diagnostic/rs-reopen-runner
description: >-
  RS global gate for diagnostic. Reopen and invalidation when a prior gate's pass
  criterion fails. Not parallel; load before $RS_COMMIT. Invoked by diagnostic/SKILL.md Gate routing.
meta-skill-version: 1.0.0
---

# rs-reopen-runner

Execute **RS — Reopen State Handler** (global · not parallel). Dialogue per gate contract; persistence via `$RS_COMMIT`.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Global · not parallel

Runs on invalidation trigger during any gate. No `gate-close` until `RS_COMPLETE`. After success, re-enter LoopA at reopen gate `G` (Q / E / D / X), not V / RR.

## When to load

Load this runner before `$RS_COMMIT` when:

- Prior gate pass criterion no longer holds — any participant, any gate (not only V).
- **G9:** evidence in current gate invalidates a prior gate → do not `gate-close`; load RS runner.
- Loop B upstream wrong → RS (not Loop B re-entry).
- **R** exit `rs` · **DC** user flags item · **Human Decision** upstream wrong.

Propose reopen gate `G` (Q / E / D / X); G8 before `$RS_COMMIT`.

**Prohibited:** manually invalidate gates, edit gate-state, or enumerate downstream gates.

**Not RS:** Loop B-only assumptions while Loop A holds → RR `return_r` to R.

## Consequences (script SSOT)

- Gate + payload invalidation: **`$GATE_CONTROL` only** (DAG scope; deletes downstream `gate-payloads/*.json`, strips risk when R reopens).
- Registers: **not** auto-modified — `$RS_COMMIT` only.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/rs-reopen-state-handler.md`
- Reopen gate `G` identified (Q / E / D / X) — from trigger context or user

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`; baseline before proposals (not conversation memory)
2. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
3. Confirm reopen gate `G` with user (G8)
4. Propose 3-state labeling for all register entries per gate contract Step 3; user confirms (G8)
5. `$RS_COMMIT` with `--gate <G>` and `--operations '<json array>'` (use `[]` if no register changes)
6. Pin `$CTX` from stdout (`reenter`, `gates`, `registers`, `domain_constraints`)
7. Return `RS_COMPLETE reenter=<G>` — load gate `G` runner via kernel § Gate routing

<HARD-GATE name="RS commit">
- Do **not** call `$RS_COMMIT` before G8 confirms `G` and register operations.
- Non-zero exit → stop RS, report stderr, wait for user direction.
- After success, read `reenter`, `gates`, `registers` from stdout only — do not chain `invalidate-from` / `register-batch-apply` / `sync-registers-to-doc` separately for RS.
</HARD-GATE>

## `$RS_COMMIT`

`$RS_COMMIT` (`$GATE_CONTROL --help` · `rs-commit`).

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

`RS_COMPLETE reenter=Q` (or E / D / X) · `RS_FAILED reason=...`
