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

`$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

**This workflow runs in Agent mode with path guard.**

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

#### Drafting Constraints

**Rule D1 — Code reads during drafting**

Read code files on demand (only what's relevant to the current design), never batch-load the entire codebase.

**Rule D2 — Output**

Write only `revision{N}/tech-doc.md`. It is the sole AI-generated artifact.

#### Drafting Sub-State Machine

1. Substep states: `Ready → Scoping → InDialogue → Extending → SkipConfirming → Checking`
2. Substep state is recorded in `drafting-progress.md`.
3. Reopen returns to `InDialogue`.

#### Step 0 — Entry

Read `workflow-state.md` → `evaluate_round`, `mode`, `carry_forward_ref`.

**If `evaluate_round > 0`:** read `evaluate-state.md` → `fix_severity`, `fix_severity_reason`; present to the user:

> "上轮评估结果：[fix_severity] — [fix_severity_reason]。本轮将从头重新起草。"

Resolve drafting inputs from `workflow-config.json`:

- feature → `tpt_url`
- topic → `shaping_tpt_url`
- shared meta → `tpt_meta_url`

Then dispatch Step 1 → Step 2 in order.

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
Exit condition: subagent writes `drafting-progress.md: current_step: InDialogue`.

Resolve `$RESOLVED_MODEL` for stage `scoping` (see `../_subagent.md` → `## Config Resolution`); dispatch:

```text
Load {actual $SKILL_ROOT}/tech-plan/scoping-runner/SKILL.md and follow its instructions.

## Input
REVISION_DIR:      {absolute path to revision{N}/}
DECISION_DOC_PATH: {absolute path to decision-doc.md}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`); verify `drafting-progress.md: current_step: InDialogue`. Then read `section-progress.md` and present Scoping summary (N/A-s ids, N/A-c ids, unresolved section count); enter Step 3.

#### Step 3 — InDialogue

Entry paths:

- after Step 2 — Scoping completes
- after Reopen
- after `Extending` or `SkipConfirming` routes back
- after `Checking` reports unresolved sections

Write `drafting-progress.md: current_step: InDialogue` on every parent-managed entry into this step.

**Resume Detection** (run once on each `InDialogue` entry)

1. Read `section-progress.md` → `sections`, `reopen_reasons`.
2. If there are existing `V`, `N/A-s`, `N/A-c`, or `S` sections, present a resume summary and state which section resumes next.
3. If any `D` sections remain:
   - if the section also appears in `reopen_reasons`, rewrite that section to `I`
   - otherwise rewrite that section to `X`
   - if multiple `D` sections remain, rewrite all of them to `X` and warn that the previous dialogue was interrupted
4. If an interrupted `D` section was rewritten, tell the user that the section will restart from the beginning.

**Select Section**

- Iterate top-level section keys in order and pick the first section whose status is `X`, `I`, or `!`
- skip `V`, `N/A-s`, `N/A-c`, and `S`
- write the selected section to `D`
- retain the pre-`D` status as the section's original mode discriminator

`§2` special case:

- for `§2` (Decision Anchors), showing the existing seeded content counts as pass-through confirmation
- if the user accepts it unchanged, write `V` directly
- if the user requests edits, switch to `I`-mode for that section

**`I`-mode — display and confirm**

1. Initialize the working buffer from the current `tech-doc.md` content for that section.
2. Show the working buffer and ask the user to confirm or request adjustments.
3. Loop:
   - confirmation → proceed to **Write and mark `V`**
   - adjustments → update the working buffer only, re-display it, and ask again

**`X`-mode — build from skeleton**

1. Read the current `tech-doc.md` skeleton for the section and identify required placeholders/sub-items.
2. Ask one question for the first unresolved required sub-item.
3. Loop:
   - if the user's reply contains a Reopen signal, stop the current section, rewrite it to `X`, clear the working buffer, and jump to **Reopen**
   - otherwise update the working buffer only
   - if unresolved required sub-items remain, ask the next single question
   - once all required sub-items are filled, show the draft and ask for confirmation or adjustments
   - confirmation → proceed to **Write and mark `V`**
   - adjustments → update the working buffer, re-display it, and continue the loop

Stop rule: once all required sub-items are filled, move to explicit draft confirmation; do not keep asking on AI judgment alone.

**`!`-mode — expired downstream review**

1. Read `reopen_reasons[§N]` and explain which upstream section triggered expiry.
2. Show the upstream reopen reason plus the current section content.
3. Ask the user to review this section in the changed upstream context.
4. Continue using the same confirmation loop as `I`-mode.

**Write and mark `V`**

1. Write the working buffer into `tech-doc.md` for the current section.
2. Write `sections[§N]: V` in `section-progress.md`.
3. Run **Reopen detection**.
4. Return to **Select Section**.

`tech-doc.md` write discipline:

- write the section content only once, immediately before setting `V`
- do not write intermediate dialogue states into `tech-doc.md`

**Reopen**

Only react when the user signals intent to revise a section.

1. Identify the target section; if unclear, ask the user to specify.
2. Confirm with the user before proceeding.
3. On confirmation:
   - Rewrite `sections[§N]: I`; record `reopen_reasons[§N] = <user reason>`.
   - Rewrite all downstream `V` sections to `!`; record `reopen_reasons[§M] = "reopened: §N — <title>"`.
   - If currently outside `InDialogue`, return to `InDialogue` first.
   - Re-enter **Select Section**.

**Exit condition**

- all standard sections and any registered custom sections are in `V`, `N/A-s`, or `N/A-c`
- no section remains in `I`, `X`, `D`, or `!`
- then write `drafting-progress.md: current_step: Extending`

#### Step 4 — Extending

Prompt: standard sections are complete; the user may add custom sections or reply `完成`.

For each custom section: append to `tech-doc.md`; register `§Cx: V` in `section-progress.md`. When the section looks complete, ask: "继续添加，还是完成？"

On `完成`: write `drafting-progress.md: current_step: SkipConfirming`.

#### Step 5 — SkipConfirming

Process every section currently marked `N/A-s` or `N/A-c`, one section at a time:

1. Show the section id and title.
2. Show `na_evidence[§N]`.
3. Ask whether the user confirms the skip or wants to fill the section after all.

Per section:

- confirm skip → rewrite `sections[§N]: S`
- restore section → clear `na_evidence[§N]`, remove that section's leading N/A banner from `tech-doc.md`, and rewrite `sections[§N]: X`

Batch boundary rule:

- do not jump back to `InDialogue` mid-batch
- only after all current `N/A-s` / `N/A-c` sections are processed, if any were restored to `X`, rewrite `drafting-progress.md: current_step: InDialogue` once and re-enter `InDialogue` for the full batch of restored sections

Exit condition:

- every original `N/A-s` / `N/A-c` section is now either `S` or `X`
- if none were restored to `X`, write `drafting-progress.md: current_step: Checking`

#### Step 6 — Checking

Write `drafting-progress.md: current_step: Checking` on entry and verify:

| Check | Pass condition |
|-------|----------------|
| Required standard sections | all required sections are `V` |
| Conditional standard sections | each conditional section is `V` or `S`; none remain `I`, `X`, `N/A-s`, or `N/A-c` |
| Custom sections (`§Cx`) | all registered custom sections are `V` |
| Cross-section consistency | `§5` file paths exactly match `§6` task-file references; `§4` naming-contract tokens exactly match the `§6` constraints that consume them |

If all checks pass:

1. Keep the existing top-level workflow model unchanged.
2. Write `workflow-state.md` → `current_state: Evaluating`.

If any check fails, list every failing section or consistency mismatch and route by failure type:

- remaining `I` / `X` / `!` → write `drafting-progress.md: current_step: InDialogue`
- remaining `N/A-s` / `N/A-c` → write `drafting-progress.md: current_step: SkipConfirming`
- consistency mismatch only → write `drafting-progress.md: current_step: InDialogue` and let the user choose which section to revise

### Evaluating Rules

**Entry confirmation**

Before starting evaluation, ask the user:

> "Start evaluation, or deliver directly?"

- Evaluate → read `./eval-rules.md` and follow its instructions.
- Deliver directly → write `workflow-state.md`: `current_state: ReadyForDelivery`, `skip_evaluate_requested: true`; preserve `mode`, `product_ref`, `carry_forward_ref`, `evaluate_round`. Then follow Rule R1.

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:

1. Present final `revision{N}/tech-doc.md` to user
2. Wait for explicit delivery confirmation
3. Write `revision{N}/human-delivery-gate.md`
4. Write `revision{N}/workflow-state.md` → `current_state: Delivered`

<DELIVERY-GATE>
Before presenting next stages to the user, read `../_transitions.md` and follow the Stage Transitions rules.
</DELIVERY-GATE>

---
