---
name: tech-doc-workflow
description: >-
  Use when: 技术方案, 技术设计, tech design, tech-doc, 技术文档, 架构设计,
  技术规格, 技术实现方案, tech-doc workflow, 技术文档流程, 技术文档状态迁移,
  lulu-dev-workflow tech, E1 E2 E3 评估, tech review, tech delivered.
disable-model-invocation: true
---

# tech-doc-workflow

Drive a tech document workflow with explicit per-session state files and a hook
that gates state transitions.

**Scope:** Tech document workflow only. Supports two run-modes: `product`（产品需求驱动）and `tech`（纯技改，无 product-doc）。
**Scripts location (after install):** `~/.cursor/skills/lulu-dev-workflow/tech/scripts/`
**This workflow runs entirely in Plan mode.**

---

## Commands

### `install` — Machine-level, run once

```bash
mkdir -p ~/.cursor/skills/lulu-dev-workflow/tech/scripts

for f in SKILL.md transition-whitelist.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/tech/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/tech/$f
done

for f in workflow_common.py hook_guard.py start.py init.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/tech/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/tech/scripts/$f
done
```

After install, run `tech-doc-workflow init` in the target project.

---

### `init` — Project-level, run once per project

Registers the tech hook into `.cursor/hooks.json` and ensures `workflow-config.json`
has a `tech` section.

```bash
cd <project-root>
python3 ~/.cursor/skills/lulu-dev-workflow/tech/scripts/init.py \
  --project-root "$(pwd)"
```

After init, verify `.cursor/lulu-dev-workflow/workflow-config.json` has the `tech`
block. Fill in `ac_url` if an architecture-constraints document exists.

---

### `start` — Session-level, run before each tech document

> Prerequisite: `init` has been run.

**Step 1: Determine conversation ID**

```bash
ls ~/.cursor/projects/*/agent-transcripts/ | tail -5
```

The most recent `.jsonl` filename (excluding `.jsonl`) is the current conversation ID.

**Step 2: Determine run-mode**

If the user has not provided a `product-doc.md` path, ask:

> 「当前任务是纯技改（无产品文档）吗？还是需要提供 product-doc.md？」

| User answer | run-mode | --product-ref |
|-------------|----------|---------------|
| 纯技改，无 product-doc | `tech` | 不提供 |
| 需要 product-doc | `product` | 用户提供的绝对路径 |

Do not infer or auto-detect the path.

**Step 3: Run start**

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/tech/scripts/start.py \
  --project-root "$(pwd)" \
  --conversation-id "<uuid>" \
  --run-mode product|tech \
  [--product-ref "<absolute-path-to-product-doc.md>"]  # product 模式必填
  [--carry-forward-ref "<absolute-path-to-previous-tech-doc.md>"]  # 可选
```

`--carry-forward-ref` is optional in both modes. Provide it when re-entering
tech flow to use a previous tech-doc as the draft starting point.

---

## Session File Structure

```
.cache/lulu-dev-workflow/tech-doc/<conv_id>/
  session-state.md               ← active_doc: N (线性递增，不回退)

  revision{N}/                          ← 第 N 个技术文档
    workflow-state.md            ← current_state, evaluate_round (AI 写，Hook 校验)
    tech-doc.md                  ← 唯一的技术方案文档（唯一 AI 加工产物）
    evaluate-state.md            ← 三维评估进度追踪
    human-delivery-gate.md       ← 交付门禁

    evaluate{M}/                 ← 第 M 轮评估（线性递增）
      tech-review-e{M}1.md       ← E1：意图对齐评审
      tech-review-e{M}2.md       ← E2：代码库一致性评审
      tech-review-e{M}3.md       ← E3：方案质量评审
```

---

## State Model

States: `Drafting` → `Evaluating` → `ReadyForDelivery` → `Delivered`

Allowed transitions:
- `Drafting → Evaluating`
- `Drafting → ReadyForDelivery`  ← skip evaluate; requires `skip_evaluate_requested: true` (hook enforced)
- `Evaluating → ReadyForDelivery`  ← requires evaluate pre-conditions (hook enforced)
- `Evaluating → Drafting`  ← requires `evaluate-state.md` with `current_dimension: abandoned` (hook enforced)
- `ReadyForDelivery → Drafting`
- `ReadyForDelivery → Delivered`  ← requires `human-delivery-gate.md` (hook enforced)

Hook enforces all transition pre-conditions. Denial messages are self-explanatory.

Skipping evaluation does **not** skip delivery confirmation: all paths still use
`ReadyForDelivery → Delivered` with `human-delivery-gate.md`.

---

## Operating Rules

### General

1. Read `.cursor/lulu-dev-workflow/workflow-config.json` → `tech` section before driving the workflow.
2. Read `session-state.md` → `active_doc: N` to determine current document round.
3. `revision{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from document body or file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md` and `evaluate-state.md`.
6. This workflow runs in Plan mode. All session files are Markdown.

### Drafting Rules

**Rule D1 — Calibration routing on entry**

Read `workflow-state.md` → `evaluate_round` to determine entry path:

| Condition | Calibration | Required reads |
|-----------|-------------|----------------|
| `evaluate_round == 0`, `carry_forward_ref` empty | Mandatory (full) | product-doc.md + `ac_url` (if set) + `tpt_url` |
| `evaluate_round == 0`, `carry_forward_ref` present | Mandatory (diff) | carry_forward tech-doc.md + product-doc.md + `ac_url` (if set) |
| `evaluate_round > 0` (return from Evaluating) | Present `fix_severity` from evaluate-state.md; user decides | Per user choice (see D2) |

**Rule D2 — Re-entry calibration (evaluate_round > 0)**

Show the user: `「本轮修复严重性：[fix_severity] — [fix_severity_reason]，是否校准？」`

| User choice | Action |
|-------------|--------|
| Yes (校准) | Read `ac_url` + `tpt_url` + product-doc relevant sections (if E1 issues last round) + code files (if E2 issues last round) |
| Skip (跳过) | Proceed directly to writing |

**Rule D3 — Code reads during drafting**

Read code files on demand (only what's relevant to the current design), never batch-load the entire codebase.

**Rule D4 — Output**

Write only `revision{N}/tech-doc.md`. It is the sole AI-generated artifact.

**Rule D5 — Skip evaluate to ReadyForDelivery**

User must explicitly request (e.g.「跳过评估」「不评估直接定稿」); if ambiguous, use AskQuestion.

Write `workflow-state.md`: `current_state: ReadyForDelivery`, `evaluate_round: 0`, `skip_evaluate_requested: true`; preserve `mode`, `product_ref`, `carry_forward_ref`. Then follow Rule R1.

### Evaluating Rules

**Rule E1 — Entry sequence**

On entering Evaluating:
1. Increment `evaluate_round` in `workflow-state.md` (write `current_state: Evaluating, evaluate_round: M`)
2. Read `mode` from `workflow-state.md` to determine evaluation path
3. Initialize `evaluate-state.md` based on mode:

```
# product 模式：current_dimension: e1, e1_status: pending
# tech 模式：current_dimension: e2, e1_status: complete（预置）, e1_total_issues: 0, e1_resolved_issues: 0
current_dimension: e1|e2
e1_status: pending|complete
e2_status: pending, e3_status: pending
total_issues: 0, resolved_issues: 0
fix_severity: "", fix_severity_reason: ""
```

**Rule E2 — Dimension sequencing**

| Mode | 执行顺序 | 跳过 | E1 file | E2 file | E3 file |
|------|---------|------|---------|---------|---------|
| product | E1 → E2 → E3 | 无 | `tech-review-e{M}1.md` | `tech-review-e{M}2.md` | `tech-review-e{M}3.md` |
| tech | E2 → E3 | E1（预置 complete） | — | `tech-review-e{M}2.md` | `tech-review-e{M}3.md` |

Inputs per dimension: E1 ← product_ref + `ptc_url`; E2 ← relevant code files; E3 ← `tpef_url`.

Do not skip within the required sequence.

**Rule E3 — Per-dimension sequence**

For each dimension (example: E1):
1. Write `e1_status: in_progress`, `current_dimension: e1` to `evaluate-state.md`
2. Load inputs (see E2 table)
3. Write `evaluate{M}/tech-review-e{M}1.md` skeleton (issues list)
4. Write `e1_total_issues: K`, update `total_issues = e1_total + e3_total + e2_total`
5. Per issue: present to user with AskQuestion → user confirms → fix `revision{N}/tech-doc.md` → update review file → `e1_resolved_issues +1`
6. Write `e1_status: complete`, update `resolved_issues`

Never batch fixes. Fix one issue, write files, then proceed.

**Rule E4 — Completion**

After E3 complete:
1. Assess overall `fix_severity` (critical / medium / minor) and write `fix_severity_reason`
2. Write `evaluate-state.md` with `current_dimension: done`, `fix_severity` filled in
3. Write `workflow-state.md` → `current_state: ReadyForDelivery` (hook will validate)

**Rule E5 — Issue presentation**

Present each issue to the user via AskQuestion, one at a time:
- Option A: 确认问题，需要修复
- Option B: 忽略，不影响交付

**Rule E6 — Abandon evaluation（废弃本轮评估，回退 Drafting）**

Use only when the user **explicitly** requests to abandon the current evaluation
(e.g.「废弃评估」「放弃评估」「取消评估」「不评了」).
Do not infer; if ambiguous, use AskQuestion.

Steps（当前轮次为 M，evaluate_round = M）——顺序不可交换：

1. **Write** `revision{N}/evaluate-state.md`：将 `current_dimension` 改为 `abandoned`，其余字段保留原值。
2. **Write** `revision{N}/workflow-state.md` with:
   - `current_state: Drafting`
   - `evaluate_round: M`（保持不变，下次进入 Evaluating 递增为 M+1）
   - `skip_evaluate_requested: false`
   - Preserve `mode`, `product_ref`, `carry_forward_ref`.
3. Hook 校验 `evaluate-state.md` 的 `current_dimension == abandoned` 后放行，按 Rule D1/D2 重新进入 Drafting。

`evaluate{M}/` 目录及已生成的 review 文件完整保留（历史记录，不删除）。

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:
1. Present final `revision{N}/tech-doc.md` to user
2. Wait for explicit delivery confirmation
3. Write `revision{N}/human-delivery-gate.md`
4. Write `revision{N}/workflow-state.md` → `current_state: Delivered`

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

### revision{N}/workflow-state.md

```markdown
---
version: 1
workflow: tech-doc
mode: product
current_state: Drafting
evaluate_round: 0
skip_evaluate_requested: false
product_ref: /abs/path/.cache/lulu-dev-workflow/product/<conv_id>/revision1/product-doc.md
carry_forward_ref: ""
updated_at: 2026-05-17T09:00:00+08:00
---
```

> `mode` 由 `start.py` 写入（`product` 或 `tech`），后续状态迁移中保持不变（AI 手写 workflow-state.md 时需保留此字段）。
> `skip_evaluate_requested: true` 仅用于 `Drafting → ReadyForDelivery`（用户显式跳过评估）；`Delivered` 时可省略该字段。

### revision{N}/evaluate-state.md

```markdown
---
version: 1
phase: evaluate
current_dimension: e1

e1_status: pending
e1_total_issues: 0
e1_resolved_issues: 0

e2_status: pending
e2_total_issues: 0
e2_resolved_issues: 0

e3_status: pending
e3_total_issues: 0
e3_resolved_issues: 0

total_issues: 0
resolved_issues: 0

fix_severity: ""
fix_severity_reason: ""
---
```

### evaluate{M}/tech-review-e{M}N.md

Each review file shares the same structure; column set varies by dimension:

```markdown
# {E1|E2|E3} 评审：{意图对齐|代码库一致性|方案质量} — revision{N} · 第 {M} 轮

**评估日期：** YYYY-MM-DD
**参照：** [E1: product_ref + ptc_url / E2: 涉及代码路径 / E3: tpef_url]

| 编号 | 问题描述 | [E2 adds: 涉及文件] | [E3 adds: 维度] | 严重性 | 状态 | 用户决策 |
|------|---------|---------------------|-----------------|-------|------|---------|
| {E1|E2|E3}-1 | ... | ... | 严重/中等/一般 | ✅ 已修复 | 修复 |
```

### human-delivery-gate.md

```markdown
---
approved: true
approved_at: 2026-05-17T09:00:00+08:00
note: All E1/E2/E3 issues resolved. User confirmed delivery.
---
```

---

## product → tech 流转契约

- `product_ref`：用户显式指定，不自动推断，两个流程目录完全解耦。
- `carry_forward_ref`：re-entry 时提供，旧 tech-doc 与新 product-doc 的版本差要在 Drafting 强制校准后解决。
- Re-entry = 新迭代（新 conv_id 或新 revision{N}），不在旧目录继续。
