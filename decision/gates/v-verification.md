> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/v-verification-runner/SKILL.md`

#### V — Verification

**Prerequisites:** X closed · R closed

**Execute:**

0. **Resolve `pending` first (V entry):** List every `risk_class=pending` item. With the user, set each to `decision` (needs separate risk release) or `implementation` (handoff only). Do **not** `gate-close` V or enter RR while any `pending` remains.

1. For each **`decision`** assumption that is **High**-risk or `release_tracking`: write Verification as  
   `Method: <how to verify> / Owner: <who> / Timing: <when> / Release condition: <specific result that marks this item [已验证]>`

2. For each **`decision`** Medium/Low without tracking: write `Accepted`. Inform user they may flag any **decision** item for "release tracking" (adds it to Risk Release scope). Ask: "Do you confirm acceptance of these? Flag any for tracking." Proceed only after explicit user batch confirmation.
   **Forbidden:** `release_tracking` on `implementation` — reclassify to `decision` first if release is required.

3. For each **`implementation`** assumption (any H/M/L): write  
   `Handoff: <who / when to verify downstream>`  
   Do **not** require Release condition. On V close these become `verified` meaning **handoff recorded**, not risk released.

4. If any prior gate's pass criterion is no longer satisfied, load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md`.

**Exit:**

| Condition | Action |
|-----------|--------|
| Any **decision** High-risk or user-flagged (`release_tracking`) item exists | Proceed to Risk Release |
| No RR-scope decision items; implementation handoffs written; M/L decision batch-confirmed | Proceed to DC directly (skip Risk Release) |
| Prior gate pass criterion no longer holds | Load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` |
| Information insufficient to decide | Output "Unable to Decide" with justification (see below) |
| Intent input has fundamental error | Apply G5: exit loop, tell user to fix and restart |

**"Unable to Decide" justification:** Directions explored (≥2) · Which gate stuck and why · What would unlock it (see Human Decision section for full spec).

**Pass criterion:** No `pending` left; every `decision` High/tracked item has full Method/Owner/Timing/Release; every `implementation` has `Handoff:`; decision M/L have `Accepted` and are batch-confirmed when taking `exit=dc`.
