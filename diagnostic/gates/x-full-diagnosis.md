> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

#### X — Full Diagnosis

**Prerequisites:** D closed

**Dimension list:** If a `## Domain Constraints` section is present (loaded from a domain holder), execute **only** the dimensions listed there; skip all others. If no Domain Constraints are present, execute all five dimensions below.

**Execute one dimension, one question at a time (apply G7 for each Core question). After presenting each dimension's result, ask "Is this [dimension name] correct? (y / adjust)" before proceeding to the next. (G8)**

| # | Dimension | Core question | Pass criterion |
|---|-----------|---------------|----------------|
| 1 | Acceptance Criteria | How do we know it's done? What observable, verifiable indicators? | Criteria are observable and verifiable — not subjective feelings |
| 2 | Impact Surface | What does this decision affect? Any outside-system parties? | Impact domains enumerated, including external |
| 3 | External Dependencies | Who owns parts this depends on? What's the contract? Where is the authoritative source? How are changes confirmed? | Each dependency has contract + authoritative source + confirmation mechanism; unclear contracts → Assumption Log |
| 4 | Implementation Cost | Time, people, resources needed? Any hidden costs? | Initial estimate with sourced rationale; no guesses |
| 5 | Expected Outcome | What does implementation produce? Does it meet Acceptance Criteria? | Outcome aligned with criteria; gaps identified and transferred to Assumption Log |

**Additional pass criteria:**
- Assumptions discovered here: immediately add to Assumption Log with `[待验证]` tag (do not defer to R).
- If Expected Outcome falls short of Acceptance Criteria: flag the gap explicitly; apply Re-open & Invalidation (re-open E or D as appropriate). Do not force-pass.
