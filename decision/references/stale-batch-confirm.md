# Stale batch confirm (optional path after RS)

Use **only** after `$RS_COMMIT` succeeds and the user has confirmed **Path Batch** (light-patch batch confirm).  
If the user chose Per-gate, is uncertain, or AI does not claim light-patch → do **not** follow this file; use `stale-gate-update.md` per gate.

Design SSOT (process): `docs/domain/archive/decision/rs-patch-batch-confirm-design.md`.

## When

- Immediate post-`$RS_COMMIT` path choice (see `rs-realign-runner`) selected **Batch**.
- Align-related stale gates to update are in `Q` / `GL` / `E` / `D` / `X` (v1). Remaining stale gates (e.g. `R`) stay on Per-gate after batch.

## Steps

1. **Read old conclusions (mandatory CLI)** — `$GET_PAYLOAD --stale-only` (or `--gates …`; same as `$GATE_CONTROL get-payload`).  
   Diffs **must** use this stdout only. Do not invent prior conclusions from conversation memory. Do not Read `gate-payloads/*.json` as a workflow step.

2. **Per-gate update proposals (dialogue, no write yet)** — For each stale align gate with a payload (and any keep-only gates): change points · keep/modify/discard · draft updated payload · **incremental Diff** for the user (no full restatement without delta).

3. **Downgrade check** — If any gate needs discard of the whole conclusion, or light-patch confidence is lost → **recommend** Per-gate; obtain path choice again; do not call `batch-reclose`.

4. **Checklist confirm** — Present one change list. User confirms once → continue. Reject / uncertain → Path Per-gate (`stale-gate-update.md`); no writes.

5. **`$BATCH_RECLOSE --payloads '<json object>'`** — Only after checklist confirm.
   Payload keys = consecutive `GATE_ORDER` prefix from current `active_gate`, each gate `stale`, subset of `Q/GL/E/D/X`.  
   Non-zero → stop, report stderr; state and payloads must be unchanged (atomic).

6. **`$GATE_CONTROL resolve-context`** — Re-pin `$CTX` from stdout.

7. Return `BATCH_COMPLETE active_gate=<G>` — parent loads the runner for `active_gate` (may still be `stale`, e.g. `R` → Per-gate).

## Rules

- Path Batch and Per-gate are mutually exclusive for one Realign recovery.
- Conversation-only "closed" does not count; only `batch-reclose` / `gate-close` persist.
- Do not delete payloads; do not call `invalidate-from`.
- On G0 hit during this dialogue → G0 runner → resume this path.
