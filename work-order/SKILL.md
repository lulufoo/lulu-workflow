---
name: work-order-workflow
description: >-
  Use when: 施工单, work-order, 任务拆分, task breakdown, TDD 准备, 施工单工作流,
  work-order workflow, 任务依赖图, task-list, 施工单评审, TWCA, WOQA,
  lulu-dev-workflow work-order.
disable-model-invocation: true
---

# work-order-workflow

将已交付的 tech-doc 拆解为可独立执行的 TDD 单元（task 文件集）。每个 task 自包含验收条件、函数规格、约束、补充和依赖，供后续 TDD session 直接使用。

**Scope：** work-order 工作流。以 Delivered tech-doc 为唯一输入，输出 task 文件集。
**Scripts location (after install):** `~/.cursor/skills/lulu-dev-workflow/work-order/scripts/`
**This workflow runs entirely in Plan mode.**

---

## Commands

### `install` — Machine-level, run once

```bash
mkdir -p ~/.cursor/skills/lulu-dev-workflow/work-order/scripts

for f in SKILL.md transition-whitelist.json 30-work-order-task-template.md 31-work-order-tasklist-template.md; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/work-order/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/work-order/$f
done

for f in workflow_common.py hook_guard.py start.py init.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/work-order/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/work-order/scripts/$f
done
```

After install, run `work-order-workflow init` in the target project.

---

### `init` — Project-level, run once per project

Registers the work-order hook into `.cursor/hooks.json` and ensures `workflow-config.json`
has a `work_order` section.

```bash
cd <project-root>
python3 ~/.cursor/skills/lulu-dev-workflow/work-order/scripts/init.py \
  --project-root "$(pwd)"
```

After init, verify `.cursor/lulu-dev-workflow/workflow-config.json` has the `work_order`
block. Fill in `twca_url` and `woqa_url` if the default GitHub URLs differ from your project's copies.

---

### `start` — Session-level, run before each work order

> Prerequisite: `init` has been run. The upstream tech-doc must be in `Delivered` state.

**Step 1: Determine conversation ID**

```bash
ls ~/.cursor/projects/*/agent-transcripts/ | tail -5
```

The most recent `.jsonl` filename (excluding `.jsonl`) is the current conversation ID.

**Step 2: Confirm tech-ref path**

Ask the user for the absolute path to the Delivered `tech-doc.md`. Do not auto-detect.

> 「请提供本次施工单对应的 tech-doc.md 绝对路径（必须是 Delivered 状态）。」

**Step 3: Run start**

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/work-order/scripts/start.py \
  --project-root "$(pwd)" \
  --conversation-id "<uuid>" \
  --tech-ref "<absolute-path-to-tech-doc.md>"
```

---

## Session File Structure

```
.cache/lulu-dev-workflow/work-order/<conv_id>/
  session-state.md               ← active_doc: N（线性递增，不回退）

  r{N}/                          ← 第 N 个施工单
    workflow-state.md            ← current_state, evaluate_round（AI 写，Hook 校验）
    task-list.md                 ← 任务索引 + Mermaid 依赖图 + 排除项
    evaluate-state.md            ← W1/W2 两维评估进度
    human-delivery-gate.md       ← 交付门禁

    evaluate{M}/                 ← 第 M 轮评估（线性递增）
      wo-review-e{M}1.md         ← W1：TWCA 交叉检测报告
      wo-review-e{M}2.md         ← W2：WOQA 质量评估报告

    tasks/                       ← 任务文件集
      t1/
        task.md                  ← TDD 执行单元（自包含）
      t2/
        task.md
      t3/
        task.md
```

---

## State Model

States: `Drafting` → `Evaluating` → `ReadyForDelivery` → `Delivered`

Allowed transitions:
- `Drafting → Evaluating`
- `Evaluating → ReadyForDelivery`  ← requires pre-conditions (hook enforced)
- `Evaluating → Drafting`
- `ReadyForDelivery → Drafting`
- `ReadyForDelivery → Delivered`  ← requires `human-delivery-gate.md`

---

## ReadyForDelivery Pre-conditions (Hook enforced)

The hook denies `Evaluating → ReadyForDelivery` unless ALL of the following hold
(`{M}` = `evaluate_round` from the incoming `workflow-state.md` frontmatter):

1. `r{N}/evaluate-state.md` exists
2. `current_dimension: done`
3. `w1_status: complete`
4. `w2_status: complete`
5. `evaluate{M}/wo-review-e{M}1.md` exists
6. `evaluate{M}/wo-review-e{M}2.md` exists

---

## Operating Rules

### General

1. Read `.cursor/lulu-dev-workflow/workflow-config.json` → `work_order` section before driving the workflow.
2. Read `session-state.md` → `active_doc: N` to determine current work-order round.
3. `r{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from document body or file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md` and `evaluate-state.md`.
6. This workflow runs in Plan mode. All session files are Markdown.

### Drafting Rules

**Rule D1 — Entry sequence**

On entering Drafting, read:
1. `workflow-state.md` → `tech_ref`, `evaluate_round`
2. `workflow-config.json` → `work_order.task_template_url`, `work_order.tasklist_template_url`
3. `tech-doc.md` (full content, from `tech_ref`)

Fetch the templates via `gh api` (same pattern as install), read their format definitions.

**Rule D2 — Two-step generation (evaluate_round == 0, first entry)**

```
第一步：生成 r{N}/task-list.md
  ├── 枚举 tech-doc 所有改动点
  ├── 按 Test-First 逻辑分组（按测试边界，不按文件）
  ├── 生成任务列表（task_id / 标题 / 目标文件 / 依赖 / TDD豁免）
  ├── 生成 Mermaid 依赖图（无环）
  ├── 记录排除项（不纳入本施工单的改动 + 原因）
  └── 等待用户确认任务拆分
         ↓ 用户确认后
第二步：逐个生成 tasks/t{N}/task.md
  ├── 先写「验收条件」（测试用例描述，正常/边界/异常场景）
  ├── 从验收条件推导「函数规格」
  ├── 从 tech-doc 显式搬运「约束」（硬性规则）
  ├── 从 tech-doc 搬运「补充」（软性上下文）
  └── 填写「依赖」（依赖的 task_id）
```

**Test-First 认知约束**：生成每个 task.md 时，先问「通过什么测试证明这个改动正确？」，再问「需要什么函数？」。验收条件写在前，函数规格写在后。

**Rule D3 — Re-entry (evaluate_round > 0)**

When returning from Evaluating or ReadyForDelivery to Drafting:
1. Read `evaluate-state.md` → check `fix_severity` and issue summary from last round
2. Do **not** re-run the two-step flow; directly edit the flagged task files
3. After fixes, prompt the user: 「所有问题已修复，是否重新进入 Evaluating？」

**Rule D4 — TDD exemption**

Pure UI / structural changes with no logic branches may set `tdd_exempt: true` in the task frontmatter.

Effects:
- `验收条件` section becomes optional (fill `N/A` if no tests)
- W2 evaluation skips Dimension 2 (TDD 合规性) and Dimension 5 (测试用例质量)

**Rule D5 — Code reads during drafting**

Read code files on demand (only what's needed to understand existing types and function signatures). Never batch-load the codebase.

**Rule D6 — Output constraint**

`task-list.md` and `tasks/t{N}/task.md` are the **only AI-generated artifacts** in Drafting. Do not create other files.

### Evaluating Rules

**Rule E1 — Entry sequence**

On entering Evaluating:
1. Increment `evaluate_round` in `workflow-state.md` (write `current_state: Evaluating, evaluate_round: M`)
2. Read `workflow-config.json` → `work_order.twca_url`, `work_order.woqa_url`
3. Initialize `evaluate-state.md`:

```
version: 1
phase: evaluate
current_dimension: w1
w1_status: pending
w1_total_issues: 0
w1_resolved_issues: 0
w2_status: pending
w2_total_issues: 0
w2_resolved_issues: 0
total_issues: 0
resolved_issues: 0
fix_severity: ""
fix_severity_reason: ""
```

**Rule E2 — W1 → W2 sequence**

Always execute W1 first, then W2. Do not skip or reorder.

| Dim | seq | Report file | Inputs |
|-----|-----|-------------|--------|
| W1 (TWCA) | 1 | `evaluate{M}/wo-review-e{M}1.md` | `task-list.md` + all `task.md` files + `tech-doc.md` + `twca_url` framework |
| W2 (WOQA) | 2 | `evaluate{M}/wo-review-e{M}2.md` | all `task.md` files + `woqa_url` framework |

**Rule E3 — W1 (TWCA) execution**

W1 checks three directions:

1. **覆盖度**：tech-doc 的每个改动点是否有对应的 task（`task-list.md` 的排除项是豁免名单）
2. **可追溯性**：每个 task 的验收条件是否能追溯回 tech-doc 的具体需求
3. **一致性**：task.md 的约束节是否与 tech-doc 的硬性要求一致，无矛盾

For each direction:
1. Load inputs, read `twca_url` framework
2. Write `evaluate{M}/wo-review-e{M}1.md` skeleton (issues list per direction)
3. Per issue: present to user via AskQuestion → user decides → fix task file → update review file immediately
4. Never batch-fix. One issue, one fix, one file update.

**Rule E4 — W2 (WOQA) execution**

W2 checks 6 dimensions (adapted from WOQA for spec documents):

| 维度 | 检查内容 | tdd_exempt 豁免 |
|------|---------|----------------|
| 1. 粒度 | 每个 task 是否对应 1–3 个函数变更，单 TDD session 可完成 | 否 |
| 2. TDD 合规性 | 验收条件是否在函数规格之前，是否遵守 Test-First 顺序 | **跳过** |
| 3. 规格完整性 | 函数签名完整，验收条件无空洞，无 TBD | 否 |
| 4. 约束说明 | 硬性规则是否完整搬运自 tech-doc | 否 |
| 5. 测试用例质量 | 是否覆盖正常/边界/异常场景 | **跳过** |
| 6. 依赖关系 | 依赖图无循环，执行顺序合理 | 否 |

Same per-issue flow as W1: present → user decides → fix → update file immediately.

**Rule E5 — Completion**

After W2 complete:
1. Assess overall `fix_severity` (critical / medium / minor) and write `fix_severity_reason`
2. Write `evaluate-state.md` with `current_dimension: done`, all statuses `complete`
3. Write `workflow-state.md` → `current_state: ReadyForDelivery` (hook will validate)

**Rule E6 — Issue presentation**

Present each issue via AskQuestion, one at a time:
- Option A: 确认问题，需要修复
- Option B: 忽略，不影响交付

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:
1. Display final `task-list.md` summary (task count, dependency graph, any exclusions)
2. Wait for explicit delivery confirmation from user
3. Write `r{N}/human-delivery-gate.md`
4. Write `r{N}/workflow-state.md` → `current_state: Delivered`
5. Output the full list of `tasks/t{N}/task.md` paths for the TDD session to consume

---

## Session File Formats

### session-state.md

```markdown
---
version: 1
active_doc: 1
updated_at: 2026-05-17T09:00:00+08:00
---
```

### r{N}/workflow-state.md

```markdown
---
version: 1
workflow: work-order
current_state: Drafting
evaluate_round: 0
tech_ref: /abs/path/.cache/lulu-dev-workflow/tech/<conv_id>/r1/tech-doc.md
updated_at: 2026-05-17T09:00:00+08:00
---
```

> `tech_ref` is set by `start.py` and must be preserved in all subsequent writes to `workflow-state.md`.

### r{N}/evaluate-state.md

```markdown
---
version: 1
phase: evaluate
current_dimension: w1

w1_status: pending
w1_total_issues: 0
w1_resolved_issues: 0

w2_status: pending
w2_total_issues: 0
w2_resolved_issues: 0

total_issues: 0
resolved_issues: 0

fix_severity: ""
fix_severity_reason: ""
---
```

### evaluate{M}/wo-review-e{M}1.md (W1 TWCA)

```markdown
# W1 评审：TWCA 交叉检测 — r{N} · 第 {M} 轮

**评估日期：** YYYY-MM-DD
**Tech 参照：** [tech_ref 路径]
**W1 框架：** [twca_url]

## 方向 1：覆盖度

| 编号 | tech-doc 改动点 | 对应 task | 状态 | 用户决策 |
|------|--------------|---------|------|---------|
| W1-1 | ... | 无对应 | ✅ 已修复 | 新增 t4 |

## 方向 2：可追溯性

| 编号 | task_id | 问题描述 | 状态 | 用户决策 |
|------|---------|---------|------|---------|

## 方向 3：一致性

| 编号 | task_id | 问题描述 | 状态 | 用户决策 |
|------|---------|---------|------|---------|
```

### evaluate{M}/wo-review-e{M}2.md (W2 WOQA)

```markdown
# W2 评审：WOQA 质量评估 — r{N} · 第 {M} 轮

**评估日期：** YYYY-MM-DD
**W2 框架：** [woqa_url]

| 编号 | task_id | 维度 | 问题描述 | 严重性 | 状态 | 用户决策 |
|------|---------|------|---------|-------|------|---------|
| W2-1 | t2 | 规格完整性 | 函数签名缺少返回类型 | 中等 | ✅ 已修复 | 修复 |
```

### human-delivery-gate.md

```markdown
---
approved: true
approved_at: 2026-05-17T09:00:00+08:00
note: W1/W2 all issues resolved. User confirmed delivery.
---
```

---

## work-order → TDD 契约

- **tech_ref**：用户在 `start` 命令显式指定，不自动推断，两个流程目录完全解耦。
- **task.md 自包含**：「约束」+「补充」节显式搬运 tech-doc 信息，TDD session 只读 task.md，无需回头读 tech-doc。
- **tdd_exempt 标记**：`tdd_exempt: true` 的任务由 TDD SKILL 跳过 Red/Green/Refactor 约束。
- **执行顺序**：按 task-list.md 依赖图拓扑排序执行各 task。

---

## Document Outputs

| File | Stage | Description |
|------|-------|-------------|
| `r{N}/task-list.md` | Drafting step 1 | 任务索引 + 依赖图 + 排除项 |
| `r{N}/tasks/t{N}/task.md` | Drafting step 2 | TDD 执行单元（自包含） |
| `r{N}/evaluate-state.md` | Evaluating | W1/W2 评估进度追踪 |
| `r{N}/evaluate{M}/wo-review-e{M}1.md` | Evaluating W1 | TWCA 交叉检测报告 |
| `r{N}/evaluate{M}/wo-review-e{M}2.md` | Evaluating W2 | WOQA 质量评估报告 |
| `r{N}/human-delivery-gate.md` | ReadyForDelivery | 用户交付确认 |
| `r{N}/workflow-state.md` | All | 当前工作流状态 |
| `session-state.md` | All | 活跃施工单指针 |
