> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

#### RR - Risk Release

**Trigger & Scope:** V gate identifies high-risk assumptions or user-flagged items. Covers all high-risk verification items + any user-flagged items (regardless of AI rating).

**Execute:**
1. For each item: check verification result against its release condition.
2. Condition met → ✅ Released; update the corresponding entry in the decision-doc.
3. Condition not met → ❌ Failed
4. After all items are resolved, proceed to the appropriate exit below.

**State model:** ⬜ Pending → ✅ Released / ❌ Failed

**Three exits after all items processed:**

1. All items ✅ Released + Assumption Log has no new `[待验证]` entries generated during LoopB  
   → write decision-doc → proceed to DC

2. All items ✅ Released + Assumption Log has new `[待验证]` entries (generated during V or RR)  
   → return to R (re-run R with the new entries; do not restart LoopA)

3. Any item ❌ Failed  
   → proceed to Human Decision
