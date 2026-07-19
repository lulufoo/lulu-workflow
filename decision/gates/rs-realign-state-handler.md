> Part of decision-workflow · global gate (not parallel) · gate contract · via `$SKILL_DIR/runners/rs-realign-runner/SKILL.md`

#### RS — Realign State Handler

**Trigger sources:** G9 (any turn: revise/contradict a closed gate) · prior pass criterion fails · Loop B upstream wrong · **R** exit `rs` · **DC** user flags item · **Human Decision** upstream wrong.

RS is a shared relay — all triggers route through RS, then RS re-enters LoopA at align gate `G`.

---

## Execution Steps

**Step 1 — Identify align point**

Determine which [LoopA] gate is being realigned (Q / GL / E / D / X). Default: earliest closed gate on the spine that the hit revises or contradicts.

**Step 2 — Mark stale (no destroy)**

Via `$RS_COMMIT`: set `active_gate = G`; mark `G` and **reached** downstream gates `stale`; leave never-reached `pending` gates untouched; **do not** delete `gate-payloads`.

**Step 3 — Register Realign Protocol**

Scope: entries with `<source>` ∈ {G + downstream gates}; upstream sources unaffected.

AI default proposals by scope and state:

- In realign scope, state `✓` → propose `[待验证]`
- All other entries → propose `[已验证]`

In all cases, AI may override the default based on semantic relevance to the realign.

1. **AI proposes 3-state labeling** — for every entry in both registers (User Prior Log + Assumption Log), apply defaults above and adjust as needed; propose one of:
   - `[已验证]` — still valid after realign; retain
   - `[待验证]` — uncertain; retain for re-assessment
   - `[失效]` — no longer relevant given the realign; mark for deletion
2. **User confirms** — user reviews AI's proposed labels; may adjust any entry
3. **Delete `[失效]` entries** — execute deletion of all confirmed-`[失效]` entries from both registers

> Registers are NOT automatically cleared by stale sweep. Only this protocol may modify register entries.

**Step 4 — Re-enter LoopA**

Output clean snapshot of both registers; re-enter LoopA at the gate identified in Step 1. That gate's runner must follow `$SKILL_DIR/references/stale-gate-update.md` while status is `stale`.
