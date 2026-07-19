> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/d-decision-runner/SKILL.md`

#### D — Decision & Scope

**Prerequisites:** E closed

**Before entering:**
1. Read `$CTX.registers.prior` from runner pipeline step 1 stdout — not conversation memory alone.
2. Read `$CTX.gl` (Grill exchanges) — compare confirmation / human–machine intents against the chosen direction and intended scope; surface conflicts before D dialogue.
3. Compare each prior against E user choice; surface conflicts or unaddressed concerns before D dialogue.
4. Address conflicts explicitly in Decision Rationale.

Do not start D dialogue until the above is complete.

**Execute:**
1. **Decision Rationale:** state which option was chosen and why, referencing E trade-offs; state why others were excluded.
2. **Scope:** state what this decision covers; then state explicit exclusions — what it does NOT cover.
3. **Landing Approach:** capture how the chosen decision lands at decision granularity — the must-do chunks in scope, their roles on that path, and dependencies (order / parallel vs. serial). Not work breakdown, scheduling, or staffing. X = *what*; Landing Approach = *how this decision lands*. (Payload field key remains `execution_approach`.)

**Confirmation (G8):** Ask user: "Does this decision rationale, scope, and landing approach look correct?" Do not declare D closed until user explicitly confirms.

**Pass criterion:** All three sub-dimensions filled; exclusions are explicit (not just "we cover X"); rationale references E trade-offs and explicitly addresses every `concern` and `excluded` prior (or states none exist); user confirmed.
