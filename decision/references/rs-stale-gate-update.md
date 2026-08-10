# RS per-gate stale update

## Entry

Use only when `$CTX.gates.<self>.status == stale` on the Per-gate recovery
path after RS. Otherwise, run the gate runner's normal Pipeline.

R is excluded: load the R runner, which owns its special stale review.

Batch selected → use `$SKILL_DIR/references/rs-stale-batch-confirm.md` instead.

## Assess

1. Identify the upstream change point that made this gate stale.
2. Use the existing conclusion from prior `$CTX` or an allowed runner read;
   classify it as keep / modify / discard.
3. Propose one updated payload. If uncertain, offer 2–3 options; do not
   silently choose rewrite magnitude.

## Confirm and persist

User confirms → `$GATE_CONTROL gate-close --gate <G> --payload '<json>'`.
Non-zero → stop, report the error, and wait for user direction.

## Handoff

Return `GATE_COMPLETE <G>`; the parent loads the next gate.

If the calling runner names a step range, stop at that range. The runner owns
close and handoff.

## Bounds

- Both light patches and full rewrites are update proposals.
- Only control commands persist state.
- Do not delete payloads manually or call `invalidate-from`.
- G0 hit → load G0 runner, then resume this path.
