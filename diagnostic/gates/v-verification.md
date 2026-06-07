> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

#### V — Verification

**Prerequisites:** X closed · R closed

**Execute:**
1. For each **High**-risk assumption: define verification action, owner, timing, and release condition.
   — **Release condition:** the specific result or state that, if achieved, marks this item ✅ Released during execution.
2. For each **Medium/Low**-risk assumption: list with acceptance rationale. Inform user they may flag any item for "release tracking" (adds it to Risk Release scope regardless of AI rating). Ask: "Do you confirm acceptance of these? Flag any for tracking." Proceed only after explicit user batch confirmation. (G8)
3. If any prior gate's pass criterion is no longer satisfied, apply Re-open & Invalidation.

**Exit:**

| Condition | Action |
|-----------|--------|
| High-risk or user-flagged items exist | Proceed to Risk Release |
| No high-risk + AI/user consensus medium/low need no explicit verification (batch-confirmed) | Write decision-doc → proceed to DC directly (skip Risk Release) |
| Prior gate pass criterion no longer holds | Trigger RS (Reopen State Handler) |
| Information insufficient to decide | Output "Unable to Decide" with justification (see below) |
| Intent input has fundamental error | Apply G5: exit loop, tell user to fix and restart |

**"Unable to Decide" justification:** Directions explored (≥2) · Which gate stuck and why · What would unlock it (see Human Decision section for full spec).

**Pass criterion:** All High-risk assumptions have an executable verification action (with owner, timing, release condition); Medium/Low-risk assumptions are explicitly listed and batch-confirmed by user; flagged items are in release tracking.
