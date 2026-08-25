# RS batch confirmation

## Entry

Use only after `$RS_COMMIT` succeeds and the user selects Batch.
Otherwise, use `$SKILL_DIR/references/rs-stale-gate-update.md` Per-gate.

## Prepare

1. Run `$GET_PAYLOAD --stale-only`.
2. For each stale align gate with a payload, prepare an incremental change list:
   change points · keep / modify / discard · draft payload.

Use CLI stdout as the only old-conclusion source. Do not reconstruct prior
conclusions from conversation memory.

## Decide

- If a full conclusion must be discarded or the patch is no longer light,
  return to Per-gate before writing.
- Otherwise, present one checklist. Continue only after user confirmation.

## Commit

1. Run `$BATCH_RECLOSE --payloads '<json object>'`.
2. Non-zero → stop, report the error, and wait for user direction.
3. Run `$GATE_CONTROL resolve-context`; pin stdout as `$CTX`.

## Handoff

Return `BATCH_COMPLETE active_gate=<G>`.
Load `active_gate`; remaining stale non-R gates continue Per-gate, while stale R
uses the R runner's special stale entry.

## Bounds

- Batch covers align gates `Q` / `GL` / `E` / `D` / `X`. R stays stale for its
  special review.
- Batch and Per-gate are mutually exclusive for one Realign recovery.
- Only control commands persist state. Do not delete payloads or call
  `invalidate-from`.
- Apply Decision [Signals](../SKILL.md#signals); then resume this path.
