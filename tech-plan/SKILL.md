---
name: tech-plan
description: >-
  Use when: 技术方案, 技术设计, tech design, tech-doc, 技术文档, 架构设计,
  技术规格, 技术实现方案, tech-doc workflow, 技术文档流程, 技术文档状态迁移,
  lulu-dev-workflow tech-plan, E1 E2 E3 评估, tech review, tech delivered.
disable-model-invocation: true
---

# tech-workflow

> **Prerequisite:** Run `diagnostic` SKILL before starting this workflow.
> The decision-doc produced by diagnostic is the required input context.
> Path: `$CACHE_DIR/<cycle_id>/tech/diagnostic/decision-doc.md`

Drive a tech document workflow with explicit per-session state files and a hook
that gates state transitions.

**Scope:** Tech document workflow only. Supports two run-modes: `product` (product-doc driven) and `tech` (pure tech, no product-doc).

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>
- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

## Commands

### `start` — Session-level, run before each tech document

> Prerequisite: `init` has been run.

**Phase 1: Identify active cycle** — See `## Session Foundation` in `../_runtime.md`

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Phase 2: Run start**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --run-mode product|tech \
  [--product-ref "<absolute-path-to-product-doc.md>"]  # required for product mode
  [--carry-forward-ref "<absolute-path-to-previous-tech-doc.md>"]  # optional
```

- `--carry-forward-ref` is optional in both modes. Provide it when re-entering
  tech flow to use a previous tech-doc as the draft starting point.
- `--run-mode`: use `product` if a `product-doc.md` path was provided (user-supplied, do not auto-detect), otherwise `tech`.

> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

---

## product → tech handoff

- `product_ref`: user-provided; never auto-detected; the two workflow directories are fully decoupled.
- `carry_forward_ref`: provided on re-entry; version delta between old tech-doc and new product-doc must be resolved via mandatory Drafting calibration.
- Re-entry = new iteration (new cycle_id or revision{N}); never continue in the old directory.

---

## State Model

Load `./transition-whitelist.json` — check `allowed_transitions` for valid transitions and `precondition` for required writes before transitioning.

---

## Operating Rules

### General

1. Read `session-state.md` → `active_doc: N` to determine current document round.
2. Read `$WORKFLOW_DIR/workflow-config.json` → `tech-plan` section before driving the workflow.
3. `workflow-state.md` is the authoritative state — always read it; never infer state from document body or file existence; write it to request a transition.
4. Use full `Write` (not `Edit`) for `workflow-state.md` and `evaluate-state.md`.
5. Path guard blocks writes outside `$CACHE_DIR/` while a session is active.
6. Read `./formats.md` before writing `workflow-state.md`, `evaluate-state.md`, or any `evaluate{M}/tech-review-*.md`.

### Drafting Rules

**If returning from Evaluating fix:** resume at Step 4 — FreeEdit; skip Steps 1–3.

#### Drafting Constraints

**Rule D1 — Code reads during drafting**

Read code files on demand (only what's relevant to the current design), never batch-load the entire codebase.

**Rule D2 — Output**

Write only `revision{N}/tech-doc.md`. It is the sole AI-generated artifact.

#### Drafting Sub-State Machine

1. Substep states: `Ready → Initializing → Scoping → Generating → FreeEdit`
2. Substep state is recorded in `drafting-progress.md`.

#### Step 0 — Entry

Read `workflow-state.md` → `evaluate_round`, `mode`, `carry_forward_ref`.

**If `evaluate_round > 0`:** read `evaluate-state.md` → `fix_severity`, `fix_severity_reason`; present to the user:

> "上轮评估结果：[fix_severity] — [fix_severity_reason]。"

Resolve drafting template keys from cycle type (sub-agents fetch via `$FETCH_TEMPLATE`):

- feature → `tech-plan` / `tpt_url`
- topic → `tech-plan` / `shaping_tpt_url`
- shared meta → `tech-plan` / `tpt_meta_url`

Use:
- `Use $FETCH_TEMPLATE tech-plan <key>`
- Read stdout as template body; on failure report error and stop current step.

Then dispatch Steps 1 → 2 → 3 in order. If returning from Evaluating fix, enter Step 4 directly.

#### Step 1 — Initializing

Entry condition: `drafting-progress.md: current_step: Ready` (or file absent).
Exit condition: subagent writes `drafting-progress.md: current_step: Scoping`.

Resolve `$RESOLVED_MODEL` for stage `initializing` (see `../_subagent.md` → `## Config Resolution`); dispatch:

```text
Load {actual $SKILL_ROOT}/tech-plan/initializing-runner/SKILL.md and follow its instructions.

## Input
REVISION_DIR:         {absolute path to revision{N}/}
DECISION_DOC_PATH:    {absolute path to decision-doc.md}
CYCLE_TYPE:           {feature | topic}
CYCLE_ID:             {cycle_id}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`); verify `drafting-progress.md: current_step: Scoping`.

#### Step 2 — Scoping

Entry condition: `drafting-progress.md: current_step: Scoping`.
Exit condition: subagent writes `drafting-progress.md: current_step: Generating`.

Resolve `$RESOLVED_MODEL` for stage `scoping` (see `../_subagent.md` → `## Config Resolution`); dispatch:

```text
Load {actual $SKILL_ROOT}/tech-plan/scoping-runner/SKILL.md and follow its instructions.

## Input
REVISION_DIR:      {absolute path to revision{N}/}
DECISION_DOC_PATH: {absolute path to decision-doc.md}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`); verify `drafting-progress.md: current_step: Generating`; enter Step 3.

#### Step 3 — Generating

Entry condition: `drafting-progress.md: current_step: Generating`.
Exit condition: subagent writes `drafting-progress.md: current_step: FreeEdit`.

Resolve `$RESOLVED_MODEL` for stage `generating` (see `../_subagent.md` → `## Config Resolution`); dispatch:

```text
Load {actual $SKILL_ROOT}/tech-plan/generating-runner/SKILL.md and follow its instructions.

## Input
REVISION_DIR:      {absolute path to revision{N}/}
DECISION_DOC_PATH: {absolute path to decision-doc.md}
CYCLE_ID:          {cycle_id}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`); verify `drafting-progress.md: current_step: FreeEdit`.

Present the full `tech-doc.md` to the user as a complete draft; enter Step 4.

#### Step 4 — FreeEdit

Entry paths:

- after Step 3 — Generating completes
- after Evaluating returns fix to Drafting (resume directly here; skip Steps 1–3)

Rules:

- User drives edits; AI assists on request.
- AI adding new sections must write `<!-- §state:U -->` immediately above the heading.
- Existing `§state:` comments are immutable — do not modify or delete.
- On user "完成": write `workflow-state.md` → `current_state: Evaluating`.

### Evaluating Rules

Before starting evaluation, ask the user:

> "Start evaluation, or deliver directly?"

- Evaluate → read `./eval-rules.md` and follow its instructions.
- Deliver directly → write `workflow-state.md`: `current_state: ReadyForDelivery`, `skip_evaluate_requested: true`; preserve `mode`, `product_ref`, `carry_forward_ref`, `evaluate_round`. Then follow Rule R1.

### ReadyForDelivery Rules

After hook allows entry to ReadyForDelivery:

1. Present final `revision{N}/tech-doc.md` to user
2. Wait for explicit delivery confirmation
3. Write `revision{N}/human-delivery-gate.md`
4. Write `revision{N}/workflow-state.md` → `current_state: Delivered`

<DELIVERY-GATE>
Before presenting next stages to the user, read `../_transitions.md` and follow the Stage Transitions rules.
</DELIVERY-GATE>

---
