> Part of diagnostic-workflow · global gate (not parallel) · gate contract · via `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md`

#### RS — Reopen State Handler

**Trigger sources:** any gate when a prior pass criterion fails (G9) · Loop B upstream wrong · **R** exit `rs` · **DC** user flags item · **Human Decision** upstream wrong.

RS is a shared relay node — all triggers route through RS, then RS re-enters LoopA.

---

## Execution Steps

**Step 1 — Identify reopen point**

Determine which [LoopA] gate is being re-opened (Q / E / D / X).

**Step 2 — Mechanically clear conclusion zones**

Clear that gate's conclusion zone and all downstream [LoopA] gates.  
Q / E / D / X / R each maintain an independent conclusion zone; clear the re-opened gate and everything after it.

**Step 3 — Register Reopen Protocol**

Reopen scope: entries with `<source>` ∈ {G + downstream gates}; upstream sources unaffected.

AI default proposals by scope and state:
- In reopen scope, state `✓` → propose `[待验证]`
- All other entries → propose `[已验证]`

In all cases, AI may override the default based on semantic relevance to the reopen.

1. **AI proposes 3-state labeling** — for every entry in both registers (User Prior Log + Assumption Log), apply defaults above and adjust as needed; propose one of:
   - `[已验证]` — still valid after reopen; retain
   - `[待验证]` — uncertain; retain for re-assessment
   - `[失效]` — no longer relevant given the reopen; mark for deletion
2. **User confirms** — user reviews AI's proposed labels; may adjust any entry
3. **Delete `[失效]` entries** — execute deletion of all confirmed-`[失效]` entries from both registers

> Registers are NOT automatically cleared by DAG propagation. Only this protocol may modify register entries.

**Step 4 — Re-enter LoopA**

Output clean snapshot of both registers; re-enter LoopA at the gate identified in Step 1.
