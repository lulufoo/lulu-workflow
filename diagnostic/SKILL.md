---
name: diagnostic
---

# diagnostic-workflow

> Framework reference: [diagnostic-decision-framework.md](https://github.com/lulufoo/ai-thinking-framework/blob/main/diagnostic-decision-framework/diagnostic-decision-framework.md)

Run a Diagnostic Decision Framework (DDF) session. **Mandatory before starting /product or /tech.**

---

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Feature Context`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/diagnostic`

---

<HARD-GATE>
Do NOT exit diagnostic or transition to /product or /tech until:
  
- All DDF gates (Q / E / D / X / R / V) have passed
- The decision-doc has been written to disk
- User has explicitly confirmed readiness to proceed

This applies to EVERY intent, regardless of perceived clarity.
"I already know what I want to build" is the most common reason to skip this —
and the most common source of wasted downstream work.
</HARD-GATE>

---

## Core Principles

1. **Expose over conclude** — the goal is to surface assumptions and risks. A conclusion is the output of verification, not the target.
2. **User prior over framework** — user's judgments, intuitions, and concerns shape the session; the framework captures and integrates them, does not override them.
3. **Log assumptions immediately** — any assumption surfaced at any gate goes into the Assumption Log right away; R organizes, does not collect.
4. **No-decision is a valid exit** — if inputs cannot be resolved, output "Unable to Decide"; do not force a direction.
5. **No-decision requires justification** — state: directions explored (≥2), stuck gate and reason, unlock condition.

---

## Re-open & Invalidation

Two global rules, applicable at any gate, any time:

**Trigger**: Any participant (AI or user) can re-open a prior gate the moment new information shows its pass criterion no longer holds — without waiting for V.

**Propagation**: When a gate is re-opened, all gates reachable from it along prerequisite dependency arrows are automatically invalidated and must be re-satisfied. Scope is determined by the DAG structure — no enumeration needed.

---

## Parallel Registers

Two registers run throughout the entire session, not attached to any single gate:

**User Prior Log** — captures user's existing judgments, preferences, concerns, and excluded options at any point in the session. Reviewed before entering D.

**Assumption Log** — captures unverified premises at any point. Organized and risk-graded at R; not collected from scratch there.

---

## Start

**Step 1: Identify active feature** — See `## Feature Context` in `../SKILL.md`

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Step 2: Confirm output path**

Decision-doc will be written to:
```
$CACHE_DIR/<feature_id>/diagnostic/decision-doc.md
```

**Step 3: Run start.py**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --feature-id "<feature_id>"
```

Creates `session-state.md` with `current_state: InProgress`.

**Do not** run start again after Delivery (`Delivered`) on the same feature — use a new feature for a new diagnostic.

---

## Execution Rules

### Global Rules

**G0. User prior capture (throughout)** — at any gate: if user states a judgment, preference, concern, or historically excluded option, capture it in the User Prior Log immediately, confirm briefly, then continue the current gate without interruption.

**G1.** One question at a time — never stack multiple questions in a single message.

**G2.** Multiple choice preferred; open-ended is fine when options are not enumerable.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. Gate status tracking** — at key moments (session start, after a gate closes, after a re-open), report each gate's status: closed (✅) / open (⬜).

**G5.** Upstream input error — if the intent input itself has a fundamental error, exit the loop; tell the user to fix the input and restart.

**G6. Override Guard (reactive)** — when an override signal is detected before all gates are closed ("skip" / "just implement it" / "go ahead" / "do it first" etc.):
1. Stop immediately — do not take any implementation action
2. State which gates have not yet closed
3. Ask the user: "Continue diagnostic or exit intentionally?"

If user confirms intentional exit → exit gracefully; mark diagnostic as incomplete in the final message.

**G7. Collect-or-Ask** (applies to all information-gathering steps):
1. First check whether information for this dimension has already been **explicitly stated** by the user in this conversation (not inferred by AI)
2. **Already stated** → must: quote the original text + restate as the answer for this dimension + one-sentence confirmation ("Is this correct?")
3. **Not stated** → ask normally

**Prohibited:** re-asking for information already stated (i.e. do not execute step 3 when step 2 applies)

**G8. Gate confirmation (all gates)** — AI cannot unilaterally declare a gate as passed. Each gate requires an explicit user confirmation step before it closes. Silence does not constitute confirmation.

---

### Gate Rules

#### Open channel (before Q)

Before entering Q, invite the user to dump existing knowledge:

> "Before we begin — share what you'd like me to know: direction preferences, concerns, or options you've already ruled out. It doesn't need to be complete; you can add more at any point."

Capture input in User Prior Log. This step is not part of Q and does not count toward Q's question quota.

---

#### Q — Problem Clarification

**Prerequisites:** None

**Execute:**
1. Ask (G7): "What triggered this decision? What problem are we solving?"
2. Ask (G7): "What are the known, non-negotiable constraints?"
   — Constraints are facts, not decisions. Do not attempt to challenge or negotiate them away.
3. Confirm understanding: restate problem and constraints in one sentence; ask if correct.

**Pass criterion:** Problem statement is clear and agreed upon; constraints enumerated.

---

#### E — Direction Exploration

**Prerequisites:** Q closed

**Execute:**
1. Propose exactly **2–3 directions** — no more, no fewer.
2. Lead with the recommended option and explain why.
3. For each direction: state core approach, pros, cons.
4. List already-excluded directions with reasons — this prevents re-litigating ruled-out paths later.
5. Ask user to choose or propose an alternative.

**Pass criterion:** ≥2 directions evaluated with explicit pros/cons; user has chosen or indicated preference.

---

#### D — Decision & Scope

**Prerequisites:** E closed · User Prior reviewed

**Before entering:** Review User Prior Log. Confirm the selected direction reflects the user's stated judgments and concerns. If there is a conflict or unaddressed concern, address it explicitly in Decision Rationale.

**Execute:**
1. **Decision Rationale:** state which option was chosen and why, referencing E trade-offs; state why others were excluded.
2. **Scope:** state what this decision covers; then state explicit exclusions — what it does NOT cover.
3. **Execution Approach:** capture the user's preferred implementation sequencing, step dependencies, and parallel vs. serial constraints. Distinct from X: X captures *what* to do; Execution Approach captures *how to sequence* it.

**Confirmation (G8):** Ask user: "Does this decision rationale, scope, and execution approach look correct?" Do not declare D closed until user explicitly confirms.

**Pass criterion:** All three sub-dimensions filled; exclusions are explicit (not just "we cover X"); rationale references E trade-offs; user confirmed.

---

#### X — Full Diagnosis

**Prerequisites:** D closed

**Execute one dimension, one question at a time (apply G7 for each Core question). After presenting each dimension's result, ask "Is this [dimension name] correct? (y / adjust)" before proceeding to the next. (G8)**

| # | Dimension | Core question | Pass criterion |
|---|-----------|---------------|----------------|
| 1 | Acceptance Criteria | How do we know it's done? What observable, verifiable indicators? | Criteria are observable and verifiable — not subjective feelings |
| 2 | Impact Surface | What does this decision affect? Any outside-system parties? | Impact domains enumerated, including external |
| 3 | External Dependencies | Who owns parts this depends on? What's the contract? Where is the authoritative source? How are changes confirmed? | Each dependency has contract + authoritative source + confirmation mechanism; unclear contracts → Assumption Log |
| 4 | Implementation Cost | Time, people, resources needed? Any hidden costs? | Initial estimate with sourced rationale; no guesses |
| 5 | Expected Outcome | What does implementation produce? Does it meet Acceptance Criteria? | Outcome aligned with criteria; gaps identified and transferred to Assumption Log |

**Additional pass criteria:**
- Assumptions discovered here: immediately add to Assumption Log (do not defer to R).
- If Expected Outcome falls short of Acceptance Criteria: flag the gap explicitly; apply Re-open & Invalidation (re-open E or D as appropriate). Do not force-pass.

---

#### R — Expose the Bets

**Prerequisites:** D closed (X and R are parallel — no ordering constraint between them)

**Execute:**
1. Review Assumption Log — do not collect from scratch. Confirm coverage is complete against D, X, and conversation history.
2. For each assumption: assign risk level and describe the consequence if it fails.

Risk levels:
- **High:** failure makes the solution unviable — requires re-decision
- **Medium:** failure causes significant rework, but solution can be adjusted
- **Low:** failure has limited impact, absorbable during execution

**Confirmation (G8):** After presenting all assumptions and risk levels, ask: "Do these risk levels look correct? You may reclassify any item." Do not declare R closed until user explicitly confirms (including any reclassifications).

**Pass criterion:** All assumptions have a risk level and consequence description; coverage review complete; user has confirmed risk classification (with any reclassifications applied).

---

#### V — Verification

**Prerequisites:** X closed · R closed

V has two distinct duties: (1) confirm that verification actions are in place for all high-risk assumptions; (2) aggregate the global diagnosis result and decide the exit.

**Execute:**
1. For each **High**-risk assumption: define verification action, owner, timing, and release condition.
   — **Release condition:** the specific result or state that, if achieved, marks this item ✅ Released during execution.
2. For each **Medium/Low**-risk assumption: list with acceptance rationale. Inform user they may flag any item for "execution-time release tracking" (adds it to Risk Release scope regardless of AI rating). Ask: "Do you confirm acceptance of these? Flag any for tracking." Proceed only after explicit user batch confirmation. (G8)
3. If any prior gate's pass criterion is no longer satisfied, apply Re-open & Invalidation.
4. Assess overall exit condition.

**Exit:**

| Condition | Action |
|-----------|--------|
| All gates pass | Write decision-doc → proceed to Delivery |
| Prior gate pass criterion no longer holds | Apply Re-open & Invalidation: re-open that gate |
| Information insufficient to decide | Output "Unable to Decide" with justification (see below) |
| Intent input has fundamental error | Apply G5: exit loop, tell user to fix and restart |

**"Unable to Decide" justification must include:**
- Directions already explored (≥2)
- Which gate is stuck and why
- What information or condition would unlock it

**Pass criterion:** All High-risk assumptions have an executable verification action (with owner, timing, release condition); Medium/Low-risk assumptions are explicitly listed and batch-confirmed by user; flagged items are in release tracking.

---

## Decision-Doc Format

Write to `$CACHE_DIR/<feature_id>/diagnostic/decision-doc.md`:

```markdown
# Decision: {title}

**Date:** YYYY-MM-DD
**Intent:** {one-line summary of the intent input}

---

## User Prior

{key judgments, preferences, concerns, and excluded options stated by the user during the session}

---

## Problem Definition

{problem statement}

**Known Constraints:** {non-negotiable constraints}

---

## Direction Comparison

| Direction | Core Approach | Pros | Cons |
|-----------|--------------|------|------|
| Option A | | | |
| Option B | | | |

**Excluded Directions:**

| Direction | Reason for Exclusion |
|-----------|---------------------|
| | |

---

## Decision Rationale

Chose **[option]** because {rationale referencing direction comparison trade-offs}.
Excluded **[option]** because {rationale}.

---

## Scope

**Applies to:** {what this decision covers}
**Explicitly excludes:** {what this decision does not cover}

---

## Acceptance Criteria

{observable, verifiable success criteria}

---

## Impact Surface

{affected domains, including outside the system}

---

## External Dependencies

| Dependency | Contract | Authoritative Source | Confirmation Mechanism |
|------------|----------|---------------------|------------------------|
| | | | |

---

## Implementation Cost

{time / people / resource estimate with rationale}

---

## Expected Outcome

{expected output quality and level; alignment with Acceptance Criteria}

---

## Assumptions & Risks

| # | Assumption | Source | Risk Level | Failure Consequence |
|---|-----------|--------|------------|---------------------|
| A1 | | | High/Medium/Low | |

---

## Verification Items

| # | Assumption | Verification Method | Owner / Timing | Release Condition | Status |
|---|-----------|---------------------|----------------|-------------------|--------|
| V1 | A{n} | | | | ⬜ |
```

---

## Self-Review (before Delivery)

Before presenting to user, scan the written decision-doc for:

1. **Completeness:** all sections filled; no empty cells in tables; User Prior captured
2. **Consistency:** Decision Rationale references E trade-offs; Verification Items map to High-risk assumptions
3. **Gap check:** if Expected Outcome < Acceptance Criteria, the gap is documented (not silently dropped)

Fix inline. No separate review round needed.

---

## Delivery

After self-review passes:
1. Present the following key sections **in the conversation** (do not just show file path):
   - Decision Rationale
   - Scope (including explicit exclusions)
   - Assumptions & Risks (all items with risk levels)
   - Verification Items
2. Ask user: "Are these decisions correct? Any items to re-open?"
3. If any item is flagged: apply Re-open & Invalidation on the corresponding gate; re-close all invalidated gates before proceeding.
4. Only after user's explicit confirmation that everything is correct, write terminal state:

```bash
# session-state.md at <feature_id>/diagnostic/session-state.md
current_state: Delivered
```

5. Tell user the next step.

> **HARD GATE — skipping `/product` or `/tech` is forbidden.**
> The decision-doc is the required input for these stages, not a substitute for them.
> Do NOT suggest `/work-order`, `/code`, or any other stage directly.

   - Product-level decision → **must** proceed to `/product`
   - Tech-level decision → **must** proceed to `/tech` (use decision-doc as context alongside product-doc if applicable)
   - Mixed (product + tech) → **must** proceed to `/product` first, then `/tech`

