---
name: product-plan
description: >-
  Use when: 产品需求, 新功能, 功能设计, 产品文档, PRD, spec, 用户故事,
  需求分析, feature request, product requirement, 功能规划, 需求文档,
  product-doc workflow, 产品文档流程, 产品文档状态迁移, lulu-dev-workflow product-plan,
  PDQA, ready for delivery, delivered.
disable-model-invocation: true
---

# product-workflow

> **Prerequisite:** Run `diagnostic` SKILL before starting this workflow.
> The decision-doc produced by diagnostic is the required input context.
> Path: `$CACHE_DIR/<cycle_id>/product/diagnostic/decision-doc.md`

Drive a product document workflow with explicit per-session state files and a
hook that gates state transitions.

**Scope:** Product document workflow only. The hook validates state transitions
and ReadyForDelivery pre-conditions; it does not evaluate spec quality or parse
the spec body.

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/product-plan`

**This workflow runs in Agent mode with path guard.** All session files are
Markdown. During an active session, writes are restricted to
`$CACHE_DIR/` by the hook guard.

---

## Stage Entry (Gate Check)

Before starting this stage, the AI must:

1. Read `features.json` (or `topics.json`) to confirm the current container type (`topic` / `feature`) and container ID.
2. Call `check_gate(cycle_id, to_stage="product-plan", cycle_type, cache_dir)` via the `hook_guard.py` script:
   - If `ok == False`: stop, output `reason` to user, do not proceed.
   - If `ok == True`: continue.
3. If container is `feature` and has `topic_id`: call `get_topic_doc(cycle_id, "product-plan", cache_dir)` to retrieve the topic reference document.
   - If path returned: inform user of the topic doc path and load it as context.
   - If `None`: skip silently.
   - If `ValueError`: stop, output error to user, do not proceed.
4. Inform user of the current cycle layer:
   - `topic` container → shaping cycle (architecture exploration)
   - `feature` container → spec cycle (implementation spec)

---

## Commands


### `start` — Session-level, run before each product document

> Prerequisite: `init` has been run.

**Step 1: Identify active cycle** — See `## Session Foundation` in `../SKILL.md`

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Step 2: Run start**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>"
```

Creates or increments `session-state.md` (`active_doc: N`) and initializes
`revision{N}/workflow-state.md` with `current_state: Drafting, evaluate_round: 0`.

Each run starts a **new** product document (revision{N+1}). To resume an existing
product document, do not run start again — read the current session files.

---

## Session File Structure

```
$CACHE_DIR/<cycle_id>/product/plan/
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

During Evaluating, revise `revision{N}/product-doc.md` in place; `evaluate{M}/` holds only `pdqa-review.md`.

---

## Operating Rules

### General Rules

**G1.** Read `$WORKFLOW_DIR/workflow-config.json` before driving the workflow.

**G2.** Session files live at `$CACHE_DIR/<cycle_id>/product/plan/revision{N}/`.
Read `session-state.md` to determine current `active_doc` (N).

**G3.** `revision{N}/workflow-state.md` is the authoritative current state — write it to request a transition.

**G4.** Never infer state from spec body or file existence; always read `workflow-state.md`.

**G5.** Only `ReadyForDelivery → Delivered` requires `revision{N}/human-delivery-gate.md`.

**G6.** Use full `Write` (not `Edit`) for `workflow-state.md`.

**G7.** This workflow runs in Agent mode. Writes outside `$CACHE_DIR/`
are blocked by the path guard hook while a session is active.

### Drafting Rules

**D1.** 根据容器类型（从 session start 时 `active-context.json → container_type` 获取）选择模板 URL：
- `topic` 容器 → 读 `workflow-config.json → product-plan.shaping_template_url`，加载 shaping 模板（13-product-shaping-template.md）
- `feature` 容器 → 读 `workflow-config.json → product-plan.template_url`，加载 spec 模板（10-product-doc-template.md）

Write only to `revision{N}/product-doc.md`. Stay in `Drafting` until the user explicitly requests evaluation.

**D2.** If `evaluate_round > 0` (returning from a prior evaluation round): read `evaluate-state.md`
and show the previous `fix_severity` as context before continuing to draft. No user response required.

### Evaluating Rules

**E1.** On entering Evaluating: write `revision{N}/evaluate-state.md` (`status: pending`, `round: M`),
then begin PDQA analysis.

**E2.** After PDQA analysis produces the issues list: write `revision{N}/evaluate{M}/pdqa-review.md`
skeleton, then update `evaluate-state.md` to `status: in_progress`.

**E3.** Present each issue to the user one at a time using the **AskQuestion tool** (never a plain
text list). Each question must offer at minimum:
- Option A: 确认问题，需要修复
- Option B: 忽略，不影响交付

Wait for the user's response before proceeding to the next issue.

**E4.** For each confirmed issue: immediately update `revision{N}/product-doc.md` (apply the fix)
and `revision{N}/evaluate{M}/pdqa-review.md` (record the resolution). Never batch updates.

**E5.** Never claim an issue is resolved without first writing the updated files.

**E6.** After all issues are resolved: assess overall `fix_severity` (critical / medium / minor) and
write `fix_severity_reason`. Then write in order:
(1) `evaluate-state.md` (`status: complete`, `fix_severity` filled in),
(2) `revision{N}/workflow-state.md` (`current_state: ReadyForDelivery`).

**E7.** **Chat output vs disk:** `revision{N}/product-doc.md` on disk is the source of truth. In chat,
link or cite the path; never paste the full document after delivery. During `Drafting` / `Evaluating`,
show only excerpts needed for the current question.

### ReadyForDelivery Rules

**R1.** After hook allows entry to ReadyForDelivery: show **title** (from `product-doc.md` H1),
**file path** (`revision{N}/product-doc.md`), and a **1–2 sentence summary** only. Do **not** paste
the full document body unless the user explicitly asks to see it. Wait for explicit delivery confirmation.

**R2.** Write `revision{N}/human-delivery-gate.md` with `approved: true` after the user confirms delivery.

**R3.** Write `revision{N}/workflow-state.md` with `current_state: Delivered`.

**R4.** Post-delivery message: delivery receipt only (state, path, optional one-line summary).
Do **not** output the full `product-doc.md` content in chat.

---

## State Behavior

### `Drafting`

Follow Rules D1–D2.

### `Evaluating`

Follow Rules E1 → E2 → loop(E3–E5) → E6 in order.
根据容器类型选择评估框架 URL：
- `topic` 容器 → 读 `workflow-config.json → product-plan.shaping_pdqa_url`，加载 shaping 评估框架（14-product-shaping-pdqa.md）
- `feature` 容器 → 读 `workflow-config.json → product-plan.pdqa_url`，加载 spec 评估框架（12-product-doc-evaluation-framework.md）
Stay in `Evaluating` or return to `Drafting` until all issues are resolved.

### `ReadyForDelivery`

Enter only after all 3 pre-conditions are met (hook enforces this).
Follow Rules R1–R3. Returning to `Drafting` is allowed if new changes are needed.

### `Delivered`

Requires `revision{N}/human-delivery-gate.md` to exist.
Follow Rule R4 after transitioning.

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
workflow: product-plan
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
fix_severity: ""
fix_severity_reason: ""
---
```

> `fix_severity`: filled after all issues resolved (Rule E6). Values: `critical` / `medium` / `minor`.
> `fix_severity_reason`: one sentence explaining the severity level.

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
workflow: product-plan
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
