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

**Scope:** Tech document workflow only. Driven by a delivered product-doc as input.
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

**Step 2: Get product-ref path**

The user must explicitly provide the path to the `product-doc.md` to base this
tech document on. Do not infer or auto-detect.

**Step 3: Run start**

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/tech/scripts/start.py \
  --project-root "$(pwd)" \
  --conversation-id "<uuid>" \
  --product-ref "<absolute-path-to-product-doc.md>" \
  [--carry-forward-ref "<absolute-path-to-previous-tech-doc.md>"]
```

`--carry-forward-ref` is optional. Provide it when re-entering tech flow after a
product update, to use a previous tech-doc as the draft starting point.

---

## Session File Structure

```
.cache/lulu-dev-workflow/tech-doc/<conv_id>/
  session-state.md               ← active_doc: N (线性递增，不回退)

  r{N}/                          ← 第 N 个技术文档
    workflow-state.md            ← current_state, evaluate_round (AI 写，Hook 校验)
    tech-doc.md                  ← 唯一的技术方案文档（唯一 AI 加工产物）
    evaluate-state.md            ← 三维评估进度追踪
    human-delivery-gate.md       ← 交付门禁

    evaluate{M}/                 ← 第 M 轮评估（线性递增）
      tech-review-e{M}1.md       ← E1：意图对齐评审
      tech-review-e{M}2.md       ← E3：代码库一致性评审
      tech-review-e{M}3.md       ← E2：方案质量评审
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

The hook denies `Evaluating → ReadyForDelivery` unless ALL of the following hold:

1. `r{N}/evaluate-state.md` exists
2. `current_dimension: done`
3. `e1_status: complete`, `e3_status: complete`, `e2_status: complete`
4. `evaluate{M}/tech-review-e{M}1.md`, `tech-review-e{M}2.md`, `tech-review-e{M}3.md` all exist

---

## Operating Rules

### General

1. Read `.cursor/lulu-dev-workflow/workflow-config.json` → `tech` section before driving the workflow.
2. Read `session-state.md` → `active_doc: N` to determine current document round.
3. `r{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
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
| Yes (校准) | Read `ac_url` + `tpt_url` + product-doc relevant sections (if E1 issues last round) + code files (if E3 issues last round) |
| Skip (跳过) | Proceed directly to writing |

**Rule D3 — Code reads during drafting**

Read code files on demand (only what's relevant to the current design), never batch-load the entire codebase.

**Rule D4 — Output**

Write only `r{N}/tech-doc.md`. It is the sole AI-generated artifact.

### Evaluating Rules

**Rule E1 — Entry sequence**

On entering Evaluating:
1. Increment `evaluate_round` in `workflow-state.md` (write `current_state: Evaluating, evaluate_round: M`)
2. Initialize `evaluate-state.md`:
   ```
   current_dimension: e1
   e1/e3/e2_status: pending
   total_issues: 0, resolved_issues: 0
   fix_severity: "", fix_severity_reason: ""
   ```

**Rule E2 — Dimension sequencing (E1 → E3 → E2, no skipping)**

Execute strictly in order. Do not start E3 until E1 is complete; do not start E2 until E3 is complete.

| Dim | seq | File | Inputs |
|-----|-----|------|--------|
| E1 | 1 | `tech-review-e{M}1.md` | `r{N}/tech-doc.md` + `product_ref` path content + `ptc_url` framework |
| E3 | 2 | `tech-review-e{M}2.md` | `r{N}/tech-doc.md` (post-E1 fixes) + relevant code files |
| E2 | 3 | `tech-review-e{M}3.md` | `r{N}/tech-doc.md` (post-E1+E3 fixes) + `tpef_url` framework |

**Rule E3 — Per-dimension sequence**

For each dimension (example: E1):
1. Write `e1_status: in_progress`, `current_dimension: e1` to `evaluate-state.md`
2. Load inputs (see E2 table)
3. Write `evaluate{M}/tech-review-e{M}1.md` skeleton (issues list)
4. Write `e1_total_issues: K`, update `total_issues = e1_total + e3_total + e2_total`
5. Per issue: present to user with AskQuestion → user confirms → fix `r{N}/tech-doc.md` → update review file → `e1_resolved_issues +1`
6. Write `e1_status: complete`, update `resolved_issues`

Never batch fixes. Fix one issue, write files, then proceed.

**Rule E4 — Completion**

After E2 complete:
1. Assess overall `fix_severity` (critical / medium / minor) and write `fix_severity_reason`
2. Write `evaluate-state.md` with `current_dimension: done`, `fix_severity` filled in
3. Write `workflow-state.md` → `current_state: ReadyForDelivery` (hook will validate)

**Rule E5 — Issue presentation**

Present each issue to the user via AskQuestion, one at a time:
- Option A: 确认问题，需要修复
- Option B: 忽略，不影响交付

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:
1. Present final `r{N}/tech-doc.md` to user
2. Wait for explicit delivery confirmation
3. Write `r{N}/human-delivery-gate.md`
4. Write `r{N}/workflow-state.md` → `current_state: Delivered`

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
workflow: tech-doc
current_state: Drafting
evaluate_round: 0
product_ref: /abs/path/.cache/lulu-dev-workflow/product/<conv_id>/r1/product-doc.md
carry_forward_ref: ""
updated_at: 2026-05-17T09:00:00+08:00
---
```

### r{N}/evaluate-state.md

```markdown
---
version: 1
phase: evaluate
current_dimension: e1

e1_status: pending
e1_total_issues: 0
e1_resolved_issues: 0

e3_status: pending
e3_total_issues: 0
e3_resolved_issues: 0

e2_status: pending
e2_total_issues: 0
e2_resolved_issues: 0

total_issues: 0
resolved_issues: 0

fix_severity: ""
fix_severity_reason: ""
---
```

### evaluate{M}/tech-review-e{M}1.md (E1)

```markdown
# E1 评审：意图对齐 — r{N} · 第 {M} 轮

**评估日期：** YYYY-MM-DD
**Product 参照：** [product_ref 路径]
**E1 框架：** [ptc_url]

| 编号 | 问题描述 | 严重性 | 状态 | 用户决策 |
|------|---------|-------|------|---------|
| E1-1 | ... | 严重/中等/一般 | ✅ 已修复 | 修复 |
```

### evaluate{M}/tech-review-e{M}2.md (E3)

```markdown
# E3 评审：代码库一致性 — r{N} · 第 {M} 轮

**评估日期：** YYYY-MM-DD
**涉及代码路径：** [主要读取的代码文件列表]

| 编号 | 问题描述 | 涉及文件 | 严重性 | 状态 | 用户决策 |
|------|---------|---------|-------|------|---------|
| E3-1 | ... | `src/foo.js` | ... | ✅ 已修复 | 修复 |
```

### evaluate{M}/tech-review-e{M}3.md (E2)

```markdown
# E2 评审：方案质量 — r{N} · 第 {M} 轮

**评估日期：** YYYY-MM-DD
**E2 框架：** [tpef_url]

| 编号 | 问题描述 | 维度 | 严重性 | 状态 | 用户决策 |
|------|---------|------|-------|------|---------|
| E2-1 | ... | 完备性 | ... | ✅ 已修复 | 修复 |
```

### human-delivery-gate.md

```markdown
---
approved: true
approved_at: 2026-05-17T09:00:00+08:00
note: All E1/E3/E2 issues resolved. User confirmed delivery.
---
```

---

## product → tech 流转契约

- `product_ref`：用户显式指定，不自动推断，两个流程目录完全解耦。
- `carry_forward_ref`：re-entry 时提供，旧 tech-doc 与新 product-doc 的版本差要在 Drafting 强制校准后解决。
- Re-entry = 新迭代（新 conv_id 或新 r{N}），不在旧目录继续。

---

## Document Outputs

| File | Stage | Description |
|------|-------|-------------|
| `r{N}/tech-doc.md` | Drafting / Evaluating | 技术方案，就地修订（唯一 AI 加工产物） |
| `r{N}/evaluate-state.md` | Evaluating | 评估进度追踪 |
| `r{N}/evaluate{M}/tech-review-e{M}1.md` | Evaluating E1 | 意图对齐评审 |
| `r{N}/evaluate{M}/tech-review-e{M}2.md` | Evaluating E3 | 代码库一致性评审 |
| `r{N}/evaluate{M}/tech-review-e{M}3.md` | Evaluating E2 | 方案质量评审 |
| `r{N}/human-delivery-gate.md` | ReadyForDelivery | 用户交付确认 |
| `r{N}/workflow-state.md` | All | 当前工作流状态 |
| `session-state.md` | All | 活跃文档指针 |
