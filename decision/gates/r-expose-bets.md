> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/r-expose-bets-runner/SKILL.md`

#### R — Expose the Bets

**Prerequisites:** X closed

**Before entering:**
1. Review User Prior from `$CTX.registers.prior` — sign off with user (G8); do not recollect via G0.
2. Review Assumption Log from `$CTX.registers.assumptions` — confirm coverage is complete against D, X, and conversation history; do not collect from scratch.

**Execute:**
1. For each assumption: assign risk level and describe the consequence if it fails.
2. Bulk assumption updates via R `gate-close` payload — not fresh G0 collection.

Risk levels:
- **High:** failure makes the solution unviable — requires re-decision
- **Medium:** failure causes significant rework, but solution can be adjusted
- **Low:** failure has limited impact, absorbable during execution

**Confirmation (G8):** After presenting all assumptions and risk levels, ask: "Do these risk levels look correct? You may reclassify any item." Do not declare R closed until user explicitly confirms (including any reclassifications).

**Pass criterion:** All assumptions have a risk level and consequence description; prior sign-off complete; coverage review complete; user has confirmed risk classification (with any reclassifications applied).

**Three exits (mutually exclusive — present proposed exit to user for confirmation; AI cannot unilaterally select):**

1. **Known failure** — an assumption is confirmed wrong or invalid  
   → load `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` → re-enter LoopA at the failed assumption's associated gate

2. **Uncertain assumptions exist** — one or more `[待验证]` entries remain after R review  
   → enter Group Loop B (V)  
   → corresponding entries remain `[待验证]`

3. **No uncertain assumptions** — all entries resolved; AI + user consensus  
   → update all remaining `[待验证]` to `[已验证]`  
   → proceed to DC
