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

**Scope:** Product document workflow only. The hook validates state transitions;
it does not evaluate spec quality or parse the spec body.

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

Creates `.cache/lulu-dev-workflow/product/<conv_id>/workflow-state.md` with
`current_state: Drafting`. Can be run again at any time to reset state.

---

## State Model

States: `Drafting` → `Evaluating` → `ReadyForDelivery` → `Delivered`

Allowed transitions:
- `Drafting → Evaluating`
- `Evaluating → ReadyForDelivery`
- `Evaluating → Drafting`
- `ReadyForDelivery → Drafting`
- `ReadyForDelivery → Delivered`

---

## Operating Rules

1. Read `.cursor/lulu-dev-workflow/workflow-config.json` before driving the workflow.
2. Session files live at `.cache/lulu-dev-workflow/product/<conversation_id>/`.
3. `workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from spec body or file existence; always read `workflow-state.md`.
5. Only `ReadyForDelivery → Delivered` requires `human-delivery-gate.md` in the same session dir.
6. Use full `Write` (not `Edit`) for `workflow-state.md`.
7. This workflow runs in Plan mode. All session files are Markdown.
8. After each issue is resolved in Evaluating: immediately update `product-doc.md`
   (apply the fix) and `pdqa-review.md` (record the resolution). Never batch updates.
9. Never claim an issue is resolved without first writing the updated files.

---

## State Behavior

### `Drafting`

- Help draft or revise the spec against `workflow-config.json → product.template_url`.
- Stay in `Drafting` until the user explicitly requests evaluation.

### `Evaluating`

- Compare the spec against `product.pdqa_url`.
- Present each issue to the user one at a time using the **AskQuestion tool** (never
  a plain text list). Each question must offer at minimum:
  - Option A: 确认问题，需要修复
  - Option B: 忽略，不影响交付
- Wait for the user's response before proceeding to the next issue.
- For each confirmed issue: immediately fix `product-doc.md` and update
  `pdqa-review.md` before moving on. Do not batch fixes.
- Stay in `Evaluating` or return to `Drafting` until all issues are resolved.

### `ReadyForDelivery`

- Enter only after evaluation is complete with all issues resolved.
- Returning to `Drafting` is allowed if new changes are needed.

### `Delivered`

- Requires `human-delivery-gate.md` to exist in the same session dir.
- Write `human-delivery-gate.md` only after the user explicitly confirms delivery.

---

## Session File Formats

### workflow-state.md

```markdown
---
version: 1
workflow: product
current_state: Evaluating
updated_at: 2026-05-17T09:00:00+08:00
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

Write the full Markdown to `.cache/lulu-dev-workflow/product/<conversation_id>/workflow-state.md`:

```markdown
---
version: 1
workflow: product
current_state: Evaluating
updated_at: 2026-05-17T00:00:00Z
---
```

The hook intercepts this write, validates the transition, and allows or denies it.

---

## Document Outputs

Write all product documents to the session directory:

| File | Stage | Description |
|------|-------|-------------|
| `product-doc.md` | Drafting / Evaluating | Product spec, revised in-place |
| `pdqa-review.md` | Evaluating | PDQA evaluation record and issue log |
| `human-delivery-gate.md` | ReadyForDelivery | User delivery confirmation |
| `workflow-state.md` | All | Current workflow state |

---

## Delivery Flow

1. Evaluation complete → write `workflow-state.md` with `current_state: ReadyForDelivery`
2. Present final spec to user; wait for explicit delivery confirmation
3. Write `human-delivery-gate.md` with `approved: true`
4. Write `workflow-state.md` with `current_state: Delivered`
5. Output the final `product-doc.md` content to the user
