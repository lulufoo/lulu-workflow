# Stale gate update (shared)

Use **only** when `$CTX.gates.<self>.status == stale` after `resolve-context`, on the **Per-gate** recovery path after RS.  
If status is not `stale`, do **not** follow this file — run the gate's normal contract.  
If the user already chose **Batch** after `$RS_COMMIT`, do **not** use this file — follow `stale-batch-confirm.md` instead (mutually exclusive for one Realign recovery).

## Steps

1. **Change points** — Relative to this gate, what upstream change (revision / contradiction) made it stale?
2. **Old conclusion disposition** — Against this gate's existing `gate-payloads/<G>.json` (via prior `$CTX` / allowed reads): which parts **keep** / **modify** / **discard**?
3. **Update proposal** — One primary update payload; if uncertain, offer 2–3 options (G2 plain text). Do not silently choose rewrite magnitude.
4. **Confirm** — User confirms → `$GATE_CONTROL gate-close --gate <G> --payload '<json>'` with the updated payload fields for this gate.
5. Return `GATE_COMPLETE <G>` — parent loads next spine runner per Gate routing (`active_gate` may still be `stale`).

If the calling runner names a step range (e.g. steps 1–3 only), stop at that range and follow the runner for close / exit handoff. The runner wins over steps 4–5.

## Rules

- No script-level carry/reset fork — both light patch and full rewrite are update proposals.
- Do not delete payloads manually; do not call `invalidate-from`.
- On G0 identification hit during this dialogue → G0 runner → resume.
