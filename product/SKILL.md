---
name: product-doc-workflow
description: >-
  Use when: 产品需求, 新功能, 功能设计, 产品文档, PRD, spec, 用户故事,
  需求分析, feature request, product requirement, 功能规划, 需求文档,
  product-doc workflow, 产品文档流程, 产品文档状态迁移, lulu-dev-workflow product,
  PDQA, ready for delivery, delivered.
disable-model-invocation: true
---

# product-doc-workflow

Drive a product document workflow with explicit per-session state files and a
hook that gates state transitions.

**Scope:** Product document workflow only. The hook validates state transitions
and ReadyForDelivery pre-conditions; it does not evaluate spec quality or parse
the spec body.

**Scripts location:** `~/.cursor/skills/lulu-dev-workflow/product/scripts/`

**This workflow runs entirely in Plan mode.** All files are Markdown; no mode
switching is required except for advanced debugging.

---

## Commands

### `install` — Machine-level, run once

```bash
mkdir -p ~/.cursor/skills/lulu-dev-workflow/product/scripts
mkdir -p ~/.cursor/skills/lulu-dev-workflow/product/templates

gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/SKILL.md" \
  --jq '.content' | base64 -d \
  > ~/.cursor/skills/lulu-dev-workflow/SKILL.md

gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/SKILL.md" \
  --jq '.content' | base64 -d \
  > ~/.cursor/skills/lulu-dev-workflow/product/SKILL.md

gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/transition-whitelist.json" \
  --jq '.content' | base64 -d \
  > ~/.cursor/skills/lulu-dev-workflow/product/transition-whitelist.json

for f in init.py hook_guard.py start.py workflow_common.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/product/scripts/$f
done

for f in workflow-config.template.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/templates/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/product/templates/$f
done
```

After install, prompt: run `product-doc-workflow init` in the target project.

---

### `init` — Project-level, run once per project

> Prerequisite: `install` has been run.

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/product/scripts/init.py \
  --project-root "$(pwd)"
```

Creates:
- `.cursor/lulu-dev-workflow/workflow-config.json`
- merges a `preToolUse` hook into `.cursor/hooks.json`
- ensures `.gitignore` includes `.cache`

After init, open `.cursor/lulu-dev-workflow/workflow-config.json` and fill in:

| Field | Description |
|-------|-------------|
| `product.template_url` | 产品文档模板 |
| `product.review_checklist_url` | 进入评估前审查清单 |
| `product.pdqa_url` | PDQA 评估框架 |

参考：`https://github.com/lulufoo/ai-software-dev/tree/main/ai-dev-workflow-framework/product_template`

---

### `start` — Session-level, run before each product document

> Prerequisite: `init` has been run. Requires current conversation ID.

**Step 1: Determine conversation ID**

The conversation ID is the UUID of the current chat session. Find it from the
agent transcripts folder:

```bash
ls ~/.cursor/projects/*/agent-transcripts/ | tail -5
```

The most recent `.jsonl` file (excluding the `.jsonl` extension) is the current
conversation ID.

**Step 2: Run start**

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/product/scripts/start.py \
  --project-root "$(pwd)" \
  --conversation-id "<uuid>"
```

Creates or increments `session-state.md` (`active_doc: N`) and initializes
`revision{N}/workflow-state.md` with `current_state: Drafting, evaluate_round: 0`.

Each run starts a **new** product document (revision{N+1}). To resume an existing
product document, do not run start again — read the current session files.

---

## Session File Structure

```
.cache/lulu-dev-workflow/product/<conv_id>/
  session-state.md               ← active_doc: N (线性递增，不回退)

  revision{N}/                          ← 第 N 个产品文档
    workflow-state.md            ← current_state, evaluate_round (AI 写，Hook 校验)
    product-doc.md               ← 当前工作草稿
    evaluate-state.md            ← pending / in_progress / complete
    human-delivery-gate.md       ← 交付门禁

    evaluate{M}/                        ← 第 M 轮 PDQA 评估
      pdqa-review.md             ← 评估记录（逐问题更新）
```

Two linear counters (non-reversible):
- `active_doc` (N): which product document in this conversation
- `evaluate_round` (M): which evaluation round within a product document

---

## State Model

States: `Drafting` → `Evaluating` → `ReadyForDelivery` → `Delivered`

Allowed transitions:
- `Drafting → Evaluating`
- `Evaluating → ReadyForDelivery`  ← requires 3 pre-conditions (see below)
- `Evaluating → Drafting`
- `ReadyForDelivery → Drafting`
- `ReadyForDelivery → Delivered`  ← requires `human-delivery-gate.md`

---

## ReadyForDelivery Pre-conditions

The hook denies `Evaluating → ReadyForDelivery` unless all of the following hold:

1. `revision{N}/evaluate-state.md` with `status: complete`
2. `revision{N}/evaluate{M}/pdqa-review.md` (where M = current `evaluate_round`)
3. `revision{N}/product-doc.md` exists and is non-empty

Do **not** create `evaluate{M}/product-doc.md`. During Evaluating, revise only
`revision{N}/product-doc.md` in place; `pdqa-review.md` records issues and resolutions.

---

## Operating Rules

1. Read `.cursor/lulu-dev-workflow/workflow-config.json` before driving the workflow.
2. Session files live at `.cache/lulu-dev-workflow/product/<conversation_id>/revision{N}/`.
   Read `session-state.md` to determine current `active_doc` (N).
3. `revision{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from spec body or file existence; always read `workflow-state.md`.
5. Only `ReadyForDelivery → Delivered` requires `revision{N}/human-delivery-gate.md`.
6. Use full `Write` (not `Edit`) for `workflow-state.md`.
7. This workflow runs in Plan mode. All session files are Markdown.
7a. On entering Evaluating: first write `revision{N}/evaluate-state.md` (`status: pending`,
    `round: M`), then begin PDQA analysis.
7b. After PDQA analysis produces the issues list: write `revision{N}/evaluate{M}/pdqa-review.md`
    skeleton, then update `evaluate-state.md` to `status: in_progress`.
7c. After all issues are resolved: write in order —
    (1) `evaluate-state.md` (`status: complete`),
    (2) `revision{N}/workflow-state.md` (`current_state: ReadyForDelivery`).
8. After each issue is resolved in Evaluating: immediately update `revision{N}/product-doc.md`
   (apply the fix) and `revision{N}/evaluate{M}/pdqa-review.md` (record the resolution). Never batch updates.
9. Never claim an issue is resolved without first writing the updated files.

---

## State Behavior

### `Drafting`

- Help draft or revise the spec against `workflow-config.json → product.template_url`.
- Write to `revision{N}/product-doc.md`.
- Stay in `Drafting` until the user explicitly requests evaluation.

### `Evaluating`

- Follow Rules 7a → 7b → loop(8) → 7c in order.
- Compare the spec against `product.pdqa_url`.
- Present each issue to the user one at a time using the **AskQuestion tool** (never
  a plain text list). Each question must offer at minimum:
  - Option A: 确认问题，需要修复
  - Option B: 忽略，不影响交付
- Wait for the user's response before proceeding to the next issue.
- For each confirmed issue: immediately fix `revision{N}/product-doc.md` and update
  `revision{N}/evaluate{M}/pdqa-review.md` before moving on. Do not batch fixes.
- Stay in `Evaluating` or return to `Drafting` until all issues are resolved.

### `ReadyForDelivery`

- Enter only after all 3 pre-conditions are met (hook enforces this).
- Returning to `Drafting` is allowed if new changes are needed.

### `Delivered`

- Requires `revision{N}/human-delivery-gate.md` to exist.
- Write `human-delivery-gate.md` only after the user explicitly confirms delivery.

---

## Session File Formats

### session-state.md

```markdown
---
version: 1
active_doc: 2
updated_at: 2026-05-17T09:00:00+08:00
---
```

### revision{N}/workflow-state.md

```markdown
---
version: 1
workflow: product
current_state: Evaluating
evaluate_round: 2
updated_at: 2026-05-17T09:00:00+08:00
---
```

### revision{N}/evaluate-state.md

```markdown
---
version: 1
phase: evaluate
round: 2
status: in_progress
total_issues: 5
resolved_issues: 3
---
```

### human-delivery-gate.md

```markdown
---
approved: true
approved_at: 2026-05-17T09:00:00+08:00
note: All PDQA issues resolved. User confirmed delivery.
---
```

---

## Transition: Writing workflow-state.md

Write the full Markdown to `revision{N}/workflow-state.md`:

```markdown
---
version: 1
workflow: product
current_state: Evaluating
evaluate_round: 1
updated_at: 2026-05-17T00:00:00Z
---
```

The hook intercepts this write, validates the transition (and pre-conditions for
ReadyForDelivery), and allows or denies it.

---

## Document Outputs

| File | Stage | Description |
|------|-------|-------------|
| `revision{N}/product-doc.md` | Drafting / Evaluating | Product spec, revised in-place |
| `revision{N}/evaluate-state.md` | Evaluating | Evaluation phase progress tracker |
| `revision{N}/evaluate{M}/pdqa-review.md` | Evaluating | PDQA evaluation record, updated per issue |
| `revision{N}/human-delivery-gate.md` | ReadyForDelivery | User delivery confirmation |
| `revision{N}/workflow-state.md` | All | Current workflow state |
| `session-state.md` | All | Active product document pointer |

---

## Delivery Flow

1. All PDQA issues resolved → follow Rule 7c (complete evaluate-state, transition to ReadyForDelivery)
2. Present final `revision{N}/product-doc.md` to user; wait for explicit delivery confirmation
3. Write `revision{N}/human-delivery-gate.md` with `approved: true`
4. Write `revision{N}/workflow-state.md` with `current_state: Delivered`
5. Output the final `revision{N}/product-doc.md` content to the user
