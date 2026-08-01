> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/r-expose-bets-runner/SKILL.md`

#### R — Expose the Bets

**Prerequisites:** X closed

**Before entering:**
1. Review User Prior from `$CTX.registers.prior` — sign off with user; do not recollect via G0.
2. Review Assumption Log from `$CTX.registers.assumptions` — confirm coverage is complete against D, X, and conversation history; do not collect from scratch.
3. Read `$CTX.gl.exchanges` in full; prioritize `gap_check`, risk-narrative answers, and confirmation-related intents; ensure risk coverage accounts for GL intents (do not rediscover them only at R).

**Execute:**
1. Present the **full** Assumption Log once. For each assumption assign together: `risk` (H/M/L), `risk_class` (`decision` | `implementation` | `pending`), and consequence if it fails.
2. Do **not** assign `risk_class` at G0 / append time — only here on the full table.
3. If it is unclear whether verification can finish before DC → mark `pending` (do not silently default to `decision`).
4. Bulk assumption updates via R `gate-close` payload — not fresh G0 collection.

**Risk levels** (impact on whether the **delivered decision** is overturned — orthogonal to `risk_class`):
- **High:** failure would seriously undermine or overturn the delivered decision (re-decision or void-level impact)
- **Medium:** failure forces a significant adjustment to the decision, but not necessarily a full overturn
- **Low:** limited impact on decision delivery; absorbable in execution

**`risk_class`:**
- **decision** — verification (or equivalent disposition) can / must complete before DC
- **implementation** — cannot meaningfully verify before DC; handoff at V; does **not** enter RR
- **pending** — gray; may leave R only via `loop_b`; must be resolved at V entry

**Confirmation:** After presenting all assumptions with risk levels and classes, ask: "Do these risk levels and classes look correct? You may reclassify any item." Do not declare R closed until user explicitly confirms (including any reclassifications).

**Pass criterion:** All assumptions have risk, `risk_class`, and consequence; prior sign-off complete; coverage review complete; user has confirmed (with any reclassifications applied).

**Three exits (mutually exclusive — present proposed exit to user for confirmation; AI cannot unilaterally select):**

1. **Known failure** — an assumption is confirmed wrong or invalid  
   → load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` → re-enter LoopA at the failed assumption's associated gate

2. **Uncertain assumptions / handoff needed** — any `[待验证]` remains, **or** any `risk_class=implementation` or `pending`  
   → enter Group Loop B (V)  
   → `exit=dc` is **forbidden** when any item is `implementation` or `pending`

3. **No uncertain assumptions** — all entries are `decision`, resolved; AI + user consensus  
   → update all remaining `[待验证]` to `[已验证]`  
   → proceed to DC
