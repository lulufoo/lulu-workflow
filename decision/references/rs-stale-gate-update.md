# RS per-gate stale update

## Entry

Per-gate recovery for a `stale` gate after RS.

1. Run this file only when `$CTX.gates.<self>.status == stale`. Otherwise, run the gate runner's normal Pipeline.
2. R is excluded. Load the R runner; it owns stale review.

## Assess

Review the existing conclusion.

1. Identify the upstream change point that made this gate stale.
2. Classify the conclusion as keep / modify / discard. Exactly one:
   - `$GET_PAYLOAD --gate <self>` returns it → use that conclusion.
   - `<self>` is `$CTX.resume_gate` with nothing saved → use this dialogue's questions and answers.
3. Propose one updated payload. If uncertain, offer 2–3 options; do not silently choose rewrite magnitude.

## After Assess

Exactly one:

- `$CTX.resume_gate` is `<self>` → stop. The caller continues its loop.
- `$CTX.resume_gate` is not `<self>` → user confirms, then `$GATE_CONTROL gate-close --gate <G> --payload '<json>'`. Return `GATE_COMPLETE <G>`; the parent loads the next gate.

## Bounds

1. Both light patches and full rewrites are update proposals.
2. Only control commands persist state.
3. Do not delete payloads manually or call `invalidate-from`.
4. Apply Decision [Signals](../SKILL.md#signals); then resume this path.
