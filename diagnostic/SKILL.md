---
name: diagnostic
---

# diagnostic-workflow

Run a Diagnostic Decision Framework (DDF) session. **Mandatory before starting /product or /tech.**

**This SKILL runs in Plan mode.**

---

<HARD-GATE>
Do NOT exit diagnostic or transition to /product or /tech until:
1. All DDF gates (Q / E / D / X / R / V) have passed
2. The decision-doc has been written to disk
3. User has explicitly confirmed readiness to proceed

This applies to EVERY intent, regardless of perceived clarity.
"I already know what I want to build" is the most common reason to skip this —
and the most common source of wasted downstream work.
</HARD-GATE>

---

## Start

**Step 1: [Optional] Load framework reference**

Load when you need to reference gate details or pass criteria:

```bash
gh api "repos/lulufoo/ai-thinking-framework/contents/diagnostic-decision-framework/diagnostic-decision-framework.md?ref=main" \
  --jq '.content' | base64 -d
```

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

**Step 4: Run start.py**

> `start.py` runs archive first: restores the current conv from `_archive/` if needed, then moves other **Delivered** convs to `_archive/<conv_id>/diagnostic/`. Non-terminal convs stay in the hot zone.

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/diagnostic/scripts/start.py \
  --project-root "$(pwd)" \
  --conversation-id "<conv_id>"
```

Creates `session-state.md` with `current_state: InProgress`.

**Do not** run start again after Delivery (`Delivered`) on the same conv — use a new conversation ID for a new diagnostic.

**Hot / cold layout:**

```
.cache/lulu-dev-workflow/diagnostic/<conv_id>/     ← hot zone
  session-state.md          ← current_state: InProgress | Delivered
  decision-doc.md

.cache/lulu-dev-workflow/_archive/<conv_id>/diagnostic/   ← cold zone (whole conv)
```

Legacy directories (only `decision-doc.md`, no `session-state.md`) are **not** auto-archived — add `session-state.md` manually or leave in hot zone.

---

## Execution Rules

### Global Rules

**G0. 用户先验捕获（全程）** — 任何门执行期间，若用户输出判断、倾向、顾虑或历史排除项，立即记入用户先验登记，简短确认后继续当前门，不打断流程。

**G1.** One question at a time — never stack multiple questions in a single message.

**G2.** Multiple choice preferred; open-ended is fine when options are not enumerable.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. 重开与失效（全程）** — 任何门执行期间，若发现某个前序门的放行标准因新信息不再成立，立即重开该门——不等 V，任何参与者均可触发。被重开门的所有下游门（沿前置依赖方向）自动失效，需重新满足放行标准。

**G5. 门状态追踪** — 在关键时刻（会话开始、门关闭后、发生重开后），报告各门状态：已放行（✅）/ 未放行（⬜）。

**G6.** Upstream input error — if the intent input itself has a fundamental error, exit the loop; tell the user to fix the input and restart.

---

### Gate Rules

#### Open channel（Q 之前）

进入 Q 之前，先做一次用户先验倾倒：

> 「在开始之前，告诉我你对这个问题已有的想法——方向倾向、顾虑或曾经排除过的选项。不需要完整，对话过程中随时可以补充。」

用户输入记入用户先验登记。此步骤不是 Q 的一部分，不占 Q 的问题配额。

---

#### Q — 问题澄清

**前置：无**

**Execute:**
1. Ask: "触发这次决策的问题是什么？"
2. Ask: "已知的、不可更改的限制有哪些？"
3. Confirm understanding: restate the problem and constraints in one sentence; ask if correct.

**Pass criterion:** Problem statement is clear and agreed upon; constraints enumerated.

---

#### E — 方向探索

**前置：Q 放行**

**Execute:**
1. Propose exactly **2–3 directions** — no more, no fewer.
2. Lead with your recommended option and explain why.
3. For each direction: state core approach, pros, cons. Include already-excluded directions with reasons.
4. Ask user to choose or propose an alternative.

**Pass criterion:** ≥2 directions evaluated with explicit pros/cons; user has chosen or indicated preference.

---

#### D — 选择与边界

**前置：E 放行 · 用户先验已审查**

**进入前：** 回顾用户先验登记，确认选定方向反映了用户带入的判断与顾虑。如有矛盾或未回应的顾虑，在选型结论中显式处理。

**Execute:**
1. **选型结论:** State which option was chosen and why, referencing E's trade-offs. State why the others were excluded.
2. **作用范围:** State what this decision covers. Then state explicit exclusions — what it does NOT cover.

**Pass criterion:** Both sub-dimensions filled; exclusions are explicit (not just "we cover X"); selection rationale references E trade-offs.

---

#### X — 全面诊断

**前置：D 放行**

**Execute one dimension, one question at a time:**

| # | Dimension | Core question |
|---|-----------|---------------|
| 1 | 验收标准 | 怎么知道做对了？用什么可观测的指标衡量？ |
| 2 | 影响面 | 这个决策会波及哪些地方？有没有系统外的受影响方？ |
| 3 | 外部依赖 | 需要和谁建立协作契约？契约内容是什么？权威来源在哪里？ |
| 4 | 实施代价 | 需要投入多少时间、人力、资源？有没有隐性成本？ |
| 5 | 结果预期 | 按这个方向实施，最终产出是什么水平？能达到验收标准吗？ |

**Pass criterion:**
- All 5 dimensions answered.
- Assumptions discovered here: immediately add to 假设流水账 (do not defer to R).
- External dependencies with unclear contracts: add to 假设流水账 as assumptions.
- If 结果预期 falls short of 验收标准: flag the gap explicitly; apply G4 (re-open E or D as appropriate). Do not force-pass.

---

#### R — 暴露赌注

**前置：D 放行**（X 与 R 并行，无先后约束）

**Execute:**
1. Review 假设流水账 — do not collect from scratch. Confirm coverage is complete against D, X, and conversation history.
2. For each assumption: assign risk level (高/中/低) and describe the consequence if it fails.

Risk levels:
- **高:** Assumption failure makes the solution unviable — requires re-decision
- **中:** Assumption failure causes significant rework, but solution can be adjusted
- **低:** Assumption failure has limited impact, absorbable during execution

**Pass criterion:** All assumptions have a risk level and consequence description; no gaps found in coverage review.

---

#### V — 验证

**前置：X 放行 · R 放行**

**Execute:**
1. For each **高**-risk assumption: define verification action, owner, timing.
2. For each **中/低**-risk assumption: explicitly acknowledge (no verification required).
3. If any prior gate's pass criterion is no longer satisfied, apply G4.
4. Assess overall exit condition.

**Exit:**

| Condition | Action |
|-----------|--------|
| All gates pass | Write decision-doc → proceed to Delivery |
| Prior gate pass criterion no longer holds | Apply G4: re-open that gate |
| Information insufficient to decide | Output 无法决策 with justification (see below) |
| Intent input has fundamental error | Apply G6: exit loop, tell user to fix and restart |

**无法决策 justification must include:**
- Directions already explored (≥2)
- Which gate is stuck and why
- What information or condition would unlock it

**Pass criterion:** All 高-risk assumptions have an executable verification action; 中/低-risk assumptions are explicitly acknowledged.

---

## Decision-Doc Format

Write to `.cache/lulu-dev-workflow/diagnostic/<conv_id>/decision-doc.md`:

```markdown
# Decision: {title}

**Date:** YYYY-MM-DD
**Intent:** {one-line summary of the intent input}

---

## 用户先验

{key judgments, preferences, concerns, and excluded options stated by the user during the session}

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

**已排除方案：**

| 方案 | 排除理由 |
|------|---------|
| | |

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

1. **Completeness:** all sections filled; no empty cells in tables; 用户先验 captured
2. **Consistency:** 选型结论 references E trade-offs; 验证项 maps to 高-risk assumptions
3. **Gap check:** if 结果预期 < 验收标准, the gap is documented (not silently dropped)

Fix inline. No separate review round needed.

---

## Delivery

After self-review passes:
1. Show user: **title**, **file path**, **1–2 sentence summary only**. Do NOT paste the full doc.
2. Ask user to review the file and confirm.
3. After confirmation, write terminal state:

```bash
# session-state.md at diagnostic/<conv_id>/session-state.md
current_state: Delivered
```

4. Tell user the next step:
   - Product-level decision → proceed to `/product`
   - Tech-level decision → proceed to `/tech` (use decision-doc as context alongside product-doc if applicable)

Delivered convs move to `_archive/<conv_id>/diagnostic/` on the next diagnostic (or any stage) start that scans the hot zone — not immediately at Delivery.
