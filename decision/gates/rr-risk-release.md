> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/rr-risk-release-runner/SKILL.md`

#### RR - Risk Release

**Trigger & Scope:** V gate identifies high-risk assumptions or user-flagged items. Covers all high-risk verification items + any user-flagged items (regardless of AI rating).

**Execute:**
1. For each item: check verification result against its Release condition (from the `Verification` column of the Assumptions & Risks table).
2. Condition met → update Status to `[已验证]` in the Assumptions & Risks table.
3. Condition not met → leave Status as `[待验证]`; proceed to Human Decision.
4. After all items are resolved, proceed to the appropriate exit below.

**Three exits after all items processed:**

1. All items `[已验证]` + Assumption Log has no new `[待验证]` entries generated during LoopB  
   → proceed to DC

2. All items `[已验证]` + Assumption Log has new `[待验证]` entries (generated during V or RR)  
   → return to R (re-run R with the new entries; do not restart LoopA)

3. Any item still `[待验证]` after verification attempt  
   → proceed to Human Decision
