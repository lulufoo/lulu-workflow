---
name: diagnostic
---

# diagnostic-workflow

Run a Diagnostic Decision Framework (DDF) session. **Mandatory before starting /product or /tech.**

**This SKILL runs in Plan mode.**

---

<HARD-GATE>
Do NOT exit diagnostic or transition to /product or /tech until:
1. All six DDF nodes (Q / E / D / X / R / V) have passed diagnosis
2. The decision-doc has been written to disk
3. User has explicitly confirmed readiness to proceed

This applies to EVERY intent, regardless of perceived clarity.
"I already know what I want to build" is the most common reason to skip this —
and the most common source of wasted downstream work.
</HARD-GATE>

---

## Start

**Step 1: Load the framework**

Read the Diagnostic Decision Framework before executing any node:

```bash
gh api "repos/lulufoo/ai-thinking-framework/contents/diagnostic-decision-framework/diagnostic-decision-framework.md?ref=main" \
  --jq '.content' | base64 -d
```

Do not proceed until the framework is loaded.

**Step 2: Determine conversation ID**

```bash
ls ~/.cursor/projects/*/agent-transcripts/ | tail -5
```

The most recent `.jsonl` filename (excluding `.jsonl`) is the current conversation ID.

**Step 3: Confirm output path**

Decision-doc will be written to:
```
.cache/lulu-dev-workflow/diagnostic/<conv_id>/decision-doc.md
```

---

## Execution Rules

### General

**G1.** One question at a time — never stack multiple questions in a single message.
**G2.** Multiple choice preferred; open-ended is fine when options are not enumerable.
**G3.** Each node has a pass criterion. Do not advance until the criterion is met.
**G4.** Back-edges are triggered from V only (see V rules). Discovering an issue mid-loop does not auto-trigger a back-edge; surface it and let V route.
**G5.** If the intent input itself is found to have an upstream error (discovered via V), exit the loop and tell the user to fix the upstream input before restarting.

---

### Node Rules

#### Q — 问题澄清

**Purpose:** Establish what problem we are solving and what the known constraints are.

**Execute:**
1. Ask: "触发这次决策的问题是什么？"
2. Ask: "已知的、不可更改的限制有哪些？"
3. Confirm understanding: restate the problem and constraints in one sentence; ask if correct.

**Pass criterion:** Problem statement is clear and agreed upon; constraints enumerated.

**If unclear:** Stay in Q; ask one focused follow-up question.

---

#### E — 方向探索

**Purpose:** Surface 2–3 viable directions with explicit trade-offs.

**Execute:**
1. Propose exactly **2–3 directions** — no more, no fewer.
2. Lead with your recommended option and explain why.
3. For each direction: state core approach, pros, cons.
4. Ask user to choose or propose an alternative.

**Pass criterion:** 2–3 directions evaluated with explicit pros/cons; user has chosen or indicated preference.

---

#### D — 选择与边界

**Purpose:** Lock in the choice and define its scope.

**Execute:**
1. **选型结论:** State which option was chosen and why, referencing E's trade-offs. State why the others were excluded.
2. **作用范围:** State what this decision covers. Then state explicit exclusions — what it does NOT cover.

**Pass criterion:** Both sub-dimensions filled; exclusions are explicit (not just "we cover X").

---

#### X — 全面诊断

**Purpose:** Thoroughly examine the chosen direction across 5 dimensions.

**Execute in sequence — one dimension, one question at a time:**

| # | Dimension | Core question |
|---|-----------|---------------|
| 1 | 验收标准 | 怎么知道做对了？用什么可观测的指标衡量？ |
| 2 | 影响面 | 这个决策会波及哪些地方？有没有系统外的受影响方？ |
| 3 | 外部依赖 | 需要和谁建立协作契约？契约内容是什么？权威来源在哪里？ |
| 4 | 实施代价 | 需要投入多少时间、人力、资源？有没有隐性成本？ |
| 5 | 结果预期 | 按这个方向实施，最终产出是什么水平？能达到验收标准吗？ |

**Pass criterion:**
- All 5 dimensions answered.
- If 结果预期 falls short of 验收标准: flag the gap explicitly and route back to E (do not force-pass).
- External dependencies with unclear contracts: transfer to R as assumptions.

---

#### R — 暴露赌注

**Purpose:** Surface every unverified premise behind each decision and boundary.

**Execute:**
1. For each item from D (选型结论, 作用范围) and X (external deps with unclear contracts): ask "what unverified premise does this depend on?"
2. For each assumption: assign risk level (高/中/低) and describe the consequence if it fails.

Risk levels:
- **高:** Assumption failure makes the solution unviable — requires re-decision
- **中:** Assumption failure causes significant rework, but solution can be adjusted
- **低:** Assumption failure has limited impact, absorbable during execution

**Pass criterion:** Every decision, boundary, and unclear dependency has been interrogated; each assumption has a risk level and consequence.

---

#### V — 验证

**Purpose:** (1) Ensure high-risk assumptions have executable verification actions. (2) Route to exit or back-edge.

**Execute:**
1. For each **高**-risk assumption: define verification action, owner, timing.
2. For each **中/低**-risk assumption: explicitly acknowledge (no verification required).
3. Assess overall pass/fail.

**Exit routing (V only):**

| Condition | Action |
|-----------|--------|
| All nodes pass | Write decision-doc → proceed to Delivery |
| Upstream intent input has a fundamental error | Exit loop; tell user to fix input and restart |
| Problem definition changed | Back-edge → Q |
| Missed a direction | Back-edge → E |
| Choice needs revision | Back-edge → D |
| Diagnosis item incomplete | Back-edge → X |
| New assumption surfaced | Back-edge → R |

**Pass criterion:** All 高-risk assumptions have an executable verification action; 中/低-risk assumptions are explicitly acknowledged.

---

## Decision-Doc Format

Write to `.cache/lulu-dev-workflow/diagnostic/<conv_id>/decision-doc.md`:

```markdown
# Decision: {title}

**Date:** YYYY-MM-DD
**Intent:** {one-line summary of the intent input}

---

## 问题域

{problem statement}

**已知约束：** {non-negotiable constraints}

---

## 方案对比

| 方案 | 核心思路 | 优势 | 劣势 |
|------|---------|------|------|
| 方案 A | | | |
| 方案 B | | | |

---

## 选型结论

选择 **[方案]**，因为 {rationale referencing E trade-offs}。
排除 **[方案]**，因为 {rationale}。

---

## 作用范围

**适用范围：** {what this decision covers}
**显式排除：** {what this decision explicitly does not cover}

---

## 验收标准

{observable, verifiable success criteria}

---

## 影响面

{affected domains, including outside the system}

---

## 外部依赖

| 依赖方 | 契约内容 | 权威来源 | 确认机制 |
|-------|---------|---------|---------|
| | | | |

---

## 实施代价

{time / people / resource estimate with rationale}

---

## 结果预期

{expected output quality and level; comparison to 验收标准}

---

## 假设与风险

| # | 假设内容 | 来源 | 风险等级 | 失效后果 |
|---|---------|------|---------|---------|
| A1 | | | 高/中/低 | |

---

## 验证项

| # | 对应假设 | 验证方式 | 负责人/时机 |
|---|---------|---------|-----------|
| V1 | A{n} | | |
```

---

## Self-Review (before Delivery)

Before presenting to user, scan the written decision-doc for:

1. **Completeness:** all sections filled; no empty cells in tables
2. **Consistency:** 选型结论 references E trade-offs; 验证项 maps to 高-risk assumptions
3. **Gap check:** if 结果预期 < 验收标准, the gap is documented (not silently dropped)

Fix inline. No separate review round needed.

---

## Delivery

After self-review passes:
1. Show user: **title**, **file path**, **1–2 sentence summary only**. Do NOT paste the full doc.
2. Ask user to review the file and confirm.
3. After confirmation, tell user the next step:
   - Product-level decision → proceed to `/product`
   - Tech-level decision → proceed to `/tech` (use decision-doc as context alongside product-doc if applicable)
