> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

#### V — Verification

**Prerequisites:** X closed · R closed

**Execute:**
1. For each **High**-risk assumption: define verification action and write it into the `Verification` column of the Assumptions & Risks table, using this format:
   `Method: <how to verify> / Owner: <who> / Timing: <when> / Release condition: <specific result that marks this item [已验证]>`
2. For each **Medium/Low**-risk assumption: write `Accepted` in the `Verification` column. Inform user they may flag any item for "release tracking" (adds it to Risk Release scope regardless of AI rating). Ask: "Do you confirm acceptance of these? Flag any for tracking." Proceed only after explicit user batch confirmation. (G8)
3. If any prior gate's pass criterion is no longer satisfied, apply Re-open & Invalidation.

**Exit:**

| Condition | Action |
|-----------|--------|
| High-risk or user-flagged items exist | Proceed to Risk Release |
| No high-risk + AI/user consensus medium/low need no explicit verification (batch-confirmed) | Proceed to DC directly (skip Risk Release) |
| Prior gate pass criterion no longer holds | Trigger RS (Reopen State Handler) |
| Information insufficient to decide | Output "Unable to Decide" with justification (see below) |
| Intent input has fundamental error | Apply G5: exit loop, tell user to fix and restart |

**"Unable to Decide" justification:** Directions explored (≥2) · Which gate stuck and why · What would unlock it (see Human Decision section for full spec).

**Pass criterion:** All High-risk assumptions have a complete Verification entry (Method / Owner / Timing / Release condition) in the Assumptions & Risks table; Medium/Low assumptions have `Accepted` in Verification and are batch-confirmed by user; flagged items are in release tracking.
