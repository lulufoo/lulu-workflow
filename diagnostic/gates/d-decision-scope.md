> Part of diagnostic-workflow · gate contract · via `$SKILL_DIR/runners/d-decision-runner/SKILL.md`

#### D — Decision & Scope

**Prerequisites:** E closed

**Before entering:**
1. Read `$CTX.registers.prior` from runner pipeline step 1 stdout — not conversation memory alone.
2. Compare each prior against E user choice; surface conflicts or unaddressed concerns before D dialogue.
3. Address conflicts explicitly in Decision Rationale.

Do not start D dialogue until the above is complete.

**Execute:**
1. **Decision Rationale:** state which option was chosen and why, referencing E trade-offs; state why others were excluded.
2. **Scope:** state what this decision covers; then state explicit exclusions — what it does NOT cover.
3. **Execution Approach:** capture the user's preferred implementation sequencing, step dependencies, and parallel vs. serial constraints. Distinct from X: X captures *what* to do; Execution Approach captures *how to sequence* it.

**Confirmation (G8):** Ask user: "Does this decision rationale, scope, and execution approach look correct?" Do not declare D closed until user explicitly confirms.

**Pass criterion:** All three sub-dimensions filled; exclusions are explicit (not just "we cover X"); rationale references E trade-offs and explicitly addresses every `concern` and `excluded` prior (or states none exist); user confirmed.
