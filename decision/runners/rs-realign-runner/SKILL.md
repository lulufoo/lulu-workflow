---
name: decision/rs-realign-runner
description: >-
  RS global gate for decision. Realign State Handler when upstream change
  requires downstream sync. Not parallel; load before $RS_COMMIT. Invoked by
  decision/SKILL.md Gate routing.
meta-skill-version: 1.0.0
---

# rs-realign-runner

Execute **RS — Realign State Handler** (global · not parallel). Dialogue per gate contract; persistence via `$RS_COMMIT` (stale sweep · no payload delete).

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Global · not parallel

Runs on upstream-change hit during any gate. No spine `gate-close` until `RS_COMPLETE`. After success, re-enter LoopA at align gate `G` (Q / GL / E / D / X), not V / RR.

## When to load

Load this runner before `$RS_COMMIT` when:

- **G9:** any turn — information revises or contradicts a closed gate's conclusion → do not `gate-close` the current gate if blocked; load RS runner.
- Prior gate pass criterion no longer holds.
- Loop B upstream wrong → RS (not Loop B re-entry).
- **R** exit `rs` · **DC** user flags item · **Human Decision** upstream wrong.

Propose align gate `G` (Q / GL / E / D / X); default earliest hit on the spine; user confirms before `$RS_COMMIT`.

**Prohibited:** manually edit gate-state, delete payloads, call `invalidate-from`, or enumerate downstream gates outside `$RS_COMMIT`.

**Not RS:** Loop B-only assumptions while Loop A holds → RR `return_r` to R.

## Consequences (script SSOT)

- Gate stale sweep: **`$GATE_CONTROL` only** (`rs-commit` / `stale-from` — marks `G` + reached downstream `stale`; **keeps** `gate-payloads`; strips risk when R is no longer closed).
- Registers: **not** auto-modified — `$RS_COMMIT` only.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/rs-realign-state-handler.md`
- Align gate `G` identified (Q / GL / E / D / X) — from trigger context or user

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`; baseline before proposals (not conversation memory)
2. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
3. Confirm align gate `G` with user
4. Propose 3-state labeling for all register entries per gate contract Step 3; user confirms
5. `$RS_COMMIT` with `--gate <G>` and `--operations '<json array>'` (use `[]` if no register changes)
6. Pin `$CTX` from stdout (`reenter`, `gates`, `registers`, `domain_constraints`)
7. **Recovery path choice** — AI states whether this looks like a light patch (one-line why) and asks: **Batch** (one checklist confirm) vs **Per-gate** (existing stale update). Uncertain / reject Batch / AI does not claim light patch → Per-gate.
8. **If Batch** — follow `$SKILL_DIR/references/stale-batch-confirm.md` to completion; return its `BATCH_COMPLETE` (do not also return `RS_COMPLETE`).
9. **If Per-gate** — Return `RS_COMPLETE reenter=<G>` — load gate `G` runner via kernel § Gate routing (`gates.G.status` is `stale`)

<HARD-GATE name="RS commit">
- Do **not** call `$RS_COMMIT` before the user confirms `G` and register operations.
- Non-zero exit → stop RS, report stderr, wait for user direction.
- After success, read `reenter`, `gates`, `registers` from stdout only — do not chain `stale-from` / `register-batch-apply` / `sync-registers-to-doc` separately for RS.
- Do **not** start Batch (`get-payload` / `batch-reclose`) before path-choice selects Batch.
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

`RS_COMPLETE reenter=Q` (or GL / E / D / X) · `BATCH_COMPLETE active_gate=<G>` · `RS_FAILED reason=...`

## Batch path

After path-choice selects Batch: `$SKILL_DIR/references/stale-batch-confirm.md` (uses `$GATE_CONTROL get-payload` / `batch-reclose`).
