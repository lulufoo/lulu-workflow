---
name: research-synthesis
description: >-
  Systematically gather and evaluate multi-source evidence for cross-domain research questions,
  producing a structured synthesis with one of three explicit exits: Consensus, Divergence, or
  Insufficient Evidence. User-invoked.
  Use when: research-synthesis, 调研综合, 系统性调研, 证据综合, 多源分析,
  我想做一次调研, 帮我研究一下, 评估这个问题的证据, 系统梳理一下
---

# research-synthesis

Given an important, externally verifiable, and information-scattered question — systematically
collect and evaluate multi-source evidence, output a structured synthesis judgment, and explicitly
land in one of three exits: `Consensus`, `Divergence`, or `Insufficient Evidence`.

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/research-synthesis`

---

## 01 Scope

### When to Use

Use when **all four conditions** are met:

1. **Important** — incorrect judgment has meaningful cost
2. **Externally verifiable** — external sources, data, cases, or original text exist
3. **Scattered information** — distributed across heterogeneous sources of varying quality
4. **Requires synthesis** — a single source cannot support a robust conclusion

| Question type | Example |
|---|---|
| State-of-the-world | "Is this phenomenon growing?" |
| Causal / explanatory | "What are the primary factors behind this outcome?" |
| Comparative / evaluative | "Which path works better under what conditions?" |
| Practice / policy | "How does the industry handle this? What has stronger evidence?" |
| Forecast / signal | "Are there early signs of a notable shift in this direction?" |

### When NOT to Use

| Question type | Reason |
|---|---|
| Has a single authoritative answer | Look up official docs, standards, or definitions directly |
| Pure value judgment or preference | Evidence cannot substitute for values |
| Requires immediate response | This SKILL's value is in careful synthesis, not speed |
| No external evidence exists at all | Cannot perform robust synthesis |
| Extremely granular execution detail | Research cost exceeds benefit |

### Relationship to lulu-dev-workflow

This SKILL is a standalone utility — it is **not** a pipeline stage and does not appear in the
Stage Transitions whitelist. It may be invoked from any stage when external evidence synthesis
is needed, most commonly:

- **Before `diagnostic`** — understanding the external landscape before entering Q gate
- **During `diagnostic` R/V gates** — when an assumption in the Assumption Log requires
  external evidence to assess (use research-synthesis, bring result back to R/V as evidence)

---

## 02 Core Model

### Four-Layer Judgment Chain

```
Layer 1: Problem Consensus    → Is this a real, evidence-supported problem?
Layer 2: Method Consensus     → Which direction is more likely correct?
Layer 3: Practice Evidence    → Has anyone made it work in a similar context?
Layer 4: Synthesis            → Core insight + next step + conditions + open questions
```

These four layers are a **conditional progression chain**, not a forced convergence pipeline.
If any layer cannot be honestly established, this SKILL must stop and report — it does not
forge the next layer.

### Three Legitimate Exits

```
Exit A: Consensus
        Multiple independent and credible sources converge on a similar judgment.

Exit B: Divergence
        Credible sources show stable, explicable disagreement.

Exit C: Insufficient Evidence
        Evidence is scarce, indirect, outdated, incomparable, or context-mismatched.
```

**Hard rules:**
- `Consensus` is not the default result — it is one possible result
- `Divergence` is a legitimate result, not a failure
- `Insufficient Evidence` is a legitimate result, not a blank
- If any layer cannot be honestly advanced, enter the appropriate exit

### Six Design Principles

1. **Confirm the problem before exploring directions** — Layer 1 cannot be skipped
2. **Establish principles before citing practice** — popular cases cannot substitute for methodological judgment
3. **Verify feasibility before giving recommendations** — do not jump to action conclusions without Layer 3
4. **Divergence is signal, not noise** — do not flatten controversy
5. **Evidence quality over source count** — do not count sources, evaluate them
6. **Recommendations are downstream, not default** — if evidence is insufficient, the next step is to gather more evidence

---

## 03 Execution

### Phase 0: Problem Scoping

**Purpose:** Define boundaries for the four-layer chain; prevent searching in the wrong direction
from the start.

**Steps:**

1. Identify implicit assumptions in the user's question
2. Decompose into at most 3 independently verifiable sub-claims
3. Execute researchability judgment:

   | Condition | Result |
   |---|---|
   | External verifiable evidence channels exist | Proceed |
   | Pure value judgment — cannot be answered by evidence | Stop at Phase 0; explain reason |
   | Too broad — no meaningful scope can be set | Ask user to narrow; stop if they cannot |

4. Classify question type:

   | Type | Core question | Priority evidence |
   |---|---|---|
   | State-of-the-world | What is the current fact? | Official data, original statistics, authoritative reports |
   | Causal / explanatory | Why does this happen? | Research design, mechanism explanation, controlled studies |
   | Comparative / evaluative | How do A and B compare? | Comparable-context comparative studies, matched cases |
   | Practice / policy | What does the industry do? What is more effective? | Practice cases with outcomes, policy texts |
   | Forecast / signal | Is this worth watching? | Time series, early cases, expert analysis |

5. Set output mode: `Research Brief` or `Decision Memo`
6. Write Problem Definition Card (must be shown to user before proceeding):

```
Research Question : [rewritten, bounded question]
Sub-claims        : [≤ 3 independently verifiable claims]
Scope             : in / out
Question Type     : [one of the 5 types above]
Output Mode       : Research Brief | Decision Memo
Researchability   : confirmed | blocked ([reason])
```

---

### Phase 1: Layer 1 — Problem Consensus

**Goal:** Confirm whether this is a real, evidence-supported problem — not a local perception,
individual experience, or amplified narrative.

**Before searching — Evidence Targeter:**

Based on question type from Phase 0, set strong vs. weak evidence standards:

| Question type | Strong evidence | Weak evidence warning |
|---|---|---|
| State-of-the-world | Official data, original statistics | Second-hand citations; no original source |
| Causal / explanatory | Studies with control group, mechanism explanation | Correlation treated as causation |
| Comparative / evaluative | Comparable-context comparative studies | Context-mismatched case comparisons |
| Practice / policy | Practice cases with outcome data | Narrative only, no verifiable results |
| Forecast / signal | Time series, multi-source early signals | Single-source predictions, no baseline |

**Search strategy:** Exact match → Semantic search → Web search

> This is the **tool invocation order** (agent execution mechanism), not source priority.
> Source priority: always target Level 1–2 sources first (official/original sources and
> high-quality secondary synthesis). Tool order does not determine source quality.

**Operations:**
1. List source types to prioritize by question type from the Evidence Targeter above
2. Seek original sources, official data, high-quality research reviews first
3. Add counter-evidence and counter-examples
4. Log each key source using the Source Log schema below
5. Judge whether the problem can be robustly stated

**Source Log schema** — apply for every claim written into a judgment (used throughout Phase 1–3):

| Field | Content |
|---|---|
| Source type | Type per the evidence ladder (01 Official / 02 Secondary synthesis / 03 Direct observation / 04 Expert analysis / 05 Interested party) |
| Claim | Claim content |
| Date | Publication date |
| Independence note | Relationship to other sources (independent / cites X / likely same origin) |
| Context fit | Match to target question context: high / medium / low |
| Bias risk | Any obvious position or interest-driven stance |
| Confidence | Strong / Moderate / Weak / Unresolvable |

**Echo chamber detection:**
- If multiple sources share highly similar key data or wording, trace back to the original source
- If all trace to the same original: record as "single source", not independent consensus
- If original cannot be found: mark ⚠️ Inferred; cannot be used to support a Consensus conclusion

**Advancement Gate 1:**

| Pass condition | Failed route |
|---|---|
| At least 2 independent sources with Confidence ≥ Moderate supporting the problem | Enter `Insufficient Evidence` or `Divergence` |

**Possible outcomes:**
- Problem consensus established → advance to Phase 2
- Stable divergence found → exit `Divergence`
- Evidence insufficient → exit `Insufficient Evidence`

---

### Phase 2: Layer 2 — Methodological Consensus

**Goal:** Confirm "if the problem is real, which direction is more likely correct."

**Operations:**
1. Extract directional or principled claims from the evidence gathered
2. For each claim, evaluate evidence quality, independence, and context fit (Source Log schema applies)
3. Classify each claim:
   - Strongly supported
   - Weakly supported
   - Contested
   - Cannot yet be judged
4. Identify main lines of divergence and their causes

**Output — Principle-Evidence Matrix:**

```
Principle → Supporting Evidence → Confidence → Applicable Conditions
```

**Advancement Gate 2:**

| Pass condition | Failed route |
|---|---|
| At least 1 principled direction with evidence support identified, OR stable divergence clearly identified | Enter `Divergence` or `Insufficient Evidence` |

**Possible outcomes:**
- Methodological consensus established → advance to Phase 3
- Stable methodological divergence → exit `Divergence`
- Principle evidence too weak → exit `Insufficient Evidence`

---

### Phase 3: Layer 3 — Practice Evidence

**Goal:** Confirm "whether these principles have proof of existence in reality."

**Operations:**
1. Search for cases, projects, policies, or practice retrospectives in similar contexts
2. Check whether cases have outcome evidence — not just narrative
3. Evaluate transferability: scale, stage, industry, resource prerequisites
4. Classify each case:
   - Strong practice proof with outcome data
   - Partial success cases only
   - Has narrative but lacks outcome evidence
   - Almost no practice evidence

Source Log schema applies to each case.

**Output — Practice Landscape:**

```
Case → Outcome → Transferability assessment
```

**Advancement Gate 3:**

| Pass condition | Failed route |
|---|---|
| At least 1 traceable case with outcome evidence | No practice evidence at all: exit `Insufficient Evidence`; contested feasibility: exit `Divergence` |

> **Layer 3 exception:** If practice evidence is scarce but Layer 1–2 conclusions are robust
> (problem and direction both established), may proceed to Layer 4 as an exception.
> Requirements: Layer 4's "Open Questions" field **must** explicitly flag this gap, and
> Confidence Notes must include ⚠️ Inferred for affected claims.
> This exception does NOT apply when there is no practice evidence whatsoever.

**Possible outcomes:**
- Feasibility strongly supported → advance to Phase 4
- Feasibility contested → exit `Divergence`
- Practice evidence insufficient → exit `Insufficient Evidence`

---

### Phase 4: Layer 4 — Synthesis

**Goal:** Compress the first three layers into a judgment the user can directly use.

**Operations:**
1. Extract the through-line connecting Layers 1–3
2. Compress into the fixed output structure below
3. If exit is not `Consensus`, explicitly write uncertainty into the summary — do not present it as complete
4. If evidence is insufficient, write "First Step" as "what evidence to gather next", not an action recommendation

**Output structure:**

- **Core Insight** — the most robust judgment that can be made from the evidence
- **First Step** — the single most actionable next move (or: next evidence to gather)
- **Applicable Conditions** — scope and prerequisites for the conclusion to hold
- **Prerequisite Check** — what must be true for the First Step to be appropriate
- **Open Questions** — unresolved issues, including any Layer 3 gaps flagged above

---

## 04 Output Format

### Default: Research Brief

```
# [Research Question]

## 1. Problem Consensus
[Is this real + supporting evidence + current exit status]

## 2. Methodological Consensus
[Which direction is more likely correct + consensus/divergence points + applicable conditions]

## 3. Practice Evidence
[Has anyone made it work + outcome evidence + transferability]

## 4. Synthesis
### Core Insight
### First Step
### Applicable Conditions
### Prerequisite Check
### Open Questions

## 5. Exit State
Consensus | Divergence | Insufficient Evidence

## 6. Confidence Notes
✅ Verified (with source) / ⚠️ Inferred / ❌ Unresolved
```

### Optional: Decision Memo

Add only on top of the completed Research Brief:

```
## 7. Decision Implications
[Action-oriented conclusions, each traceable to prior evidence]
```

**Limits:**
- Decision Memo cannot skip the four-layer structure
- All recommendations must be traceable to evidence in Sections 1–3
- If exit is `Insufficient Evidence`, recommendations must point toward gathering more evidence — not toward executing

---

## 05 Artifacts

### Path convention

```
$CACHE_DIR/research-synthesis/
  <YYYYMMDD>-<slug>/
    research-brief.md      ← primary output, always produced
    source-log.md          ← source record, always produced (accumulated through Phase 1–3)
    decision-memo.md       ← optional, only when Phase 0 output mode = Decision Memo
```

`<slug>` = 3–5 word lowercase-hyphen summary of the research question, auto-generated at Phase 0.

**Example (Cursor):**
```
.cache/cursor/lulu-dev-workflow/research-synthesis/20260604-ai-adoption-barriers/
```

### Write timing

| Artifact | When to write |
|---|---|
| `source-log.md` | Created at Phase 1 start; continuously appended through Phase 1–3 |
| `research-brief.md` | Written once at Phase 4 completion |
| `decision-memo.md` | Written at Phase 4 completion (only if output mode = Decision Memo was set in Phase 0) |

### Exit State notation

`research-brief.md` must end with:

```
## Exit State
[Consensus | Divergence | Insufficient Evidence]

## Confidence Notes
[✅ / ⚠️ / ❌ labels on major conclusions per layer]
```

---

## 06 Failure Modes

Anti-patterns to prevent at every step:

1. **Forced convergence** — writing "the industry widely believes" when no real consensus exists
2. **Source counting** — treating source quantity as truth quality, ignoring independence
3. **Case overgeneralization** — treating a few success cases as universal rules
4. **Output overreach** — giving action plans when evidence is insufficient
5. **Context loss** — ignoring differences in scale, stage, region, or organizational type
