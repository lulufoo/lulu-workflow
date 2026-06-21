> Part of diagnostic-workflow · gate contract · via `$SKILL_DIR/runners/x-full-diagnosis-runner/SKILL.md`

#### X — Full Diagnosis

**Prerequisites:** D closed

**Dimension list:** If a `## Domain Constraints` section is present (loaded from a domain holder), execute **only** the dimensions listed there; skip all others. If no Domain Constraints are present, execute all five dimensions below.

**Execute one dimension, one question at a time (apply G7 for each Core question). After presenting each dimension's result, ask "Is this [dimension name] correct? (y / adjust)" before proceeding to the next. (G8)**

| # | Dimension | Core question | Pass criterion |
|---|-----------|---------------|----------------|
| 1 | Acceptance Criteria | How do we know it's done? What observable, verifiable indicators? | Criteria are observable and verifiable — not subjective feelings |
| 2 | Impact Surface | What does this decision affect? Any outside-system parties? | Impact domains enumerated, including external |
| 3 | External Dependencies | Who owns parts this depends on? What's the contract? Where is the authoritative source? How are changes confirmed? | Each dependency has contract + authoritative source + confirmation mechanism; unclear contracts → Assumption Log |
| 4 | Implementation Sketch | What are the key changes? Any non-obvious constraints or complexity? How reversible is this change? | Key changes / Critical constraints / Reversibility all filled; unknown constraints → Assumption Log |
| 5 | Gap Check | Does the expected implementation output meet the Acceptance Criteria? Where does it fall short? | Gap explicitly recorded in `Acceptance Criteria > Gap (if any)`, or confirmed as None |

**Additional pass criteria:**
- Assumptions discovered here: load `$SKILL_DIR/runners/g0-parallel-registers-runner/SKILL.md` immediately (do not defer to R).
- If Gap (if any) is non-empty: flag the gap explicitly; load `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` (re-open E or D as appropriate). Do not force-pass.

> Dim 5 (Gap Check) does not produce a separate document section. Its result is written into `### 7.1 Acceptance Criteria > Gap (if any)` in the decision-doc.
