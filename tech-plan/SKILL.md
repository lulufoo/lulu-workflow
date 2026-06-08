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

## State Model

Load `./transition-whitelist.json` — check `allowed_transitions` for valid transitions and `precondition` for required writes before transitioning.

---

## Operating Rules

### General

1. Read `$WORKFLOW_DIR/workflow-config.json` → `tech` section before driving the workflow.
2. Read `session-state.md` → `active_doc: N` to determine current document round.
3. `revision{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from document body or file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md` and `evaluate-state.md`.
6. This workflow runs in Agent mode. Writes outside `$CACHE_DIR/`
   are blocked by the path guard hook while a session is active.

### Drafting Rules

#### Step 0 — Entry

- Read `workflow-state.md` → `evaluate_round`, `mode`, `carry_forward_ref`
- Confirm `decision-doc.md` path from the diagnostic prerequisite
- Read `## Session Foundation` in `../_runtime.md` → resolve `cycle_type`
- Substep states are managed in `drafting-progress.md` (`Ready → Scoping → InDialogue → Extending → SkipConfirming → Checking`); do not expand `workflow-state.md` states.

If `evaluate_round == 0`: resolve drafting inputs from `workflow-config.json` (feature → `tpt_url`; topic → `shaping_tpt_url`; shared meta → `tpt_meta_url`), then dispatch Step 1 → Step 2 in order.

**Rule D1 — Calibration routing (`evaluate_round > 0`)**: read `evaluate-state.md` → `fix_severity` and `fix_severity_reason`; present to user and route per Rule D2.

**Rule D2 — Re-entry calibration (evaluate_round > 0)**

Show the user: `"Fix severity this round: [fix_severity] — [fix_severity_reason]. Recalibrate?"`

| User choice | Action |
|-------------|--------|
| Yes | Read `ac_url` + `tpt_url` (feature) or `shaping_tpt_url` (topic) + product-doc relevant sections (if E1 issues last round) + code files (if E2 issues last round) |
| Skip | Proceed directly to writing |

#### Step 1 — Initializing

Only runs on first Drafting entry (`evaluate_round == 0`).

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

Only runs on first Drafting entry (`evaluate_round == 0`).

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
- after Rule D0 Scoping completes
- after Reopen
- after `Extending` or `SkipConfirming` routes back
- after `Checking` reports unresolved sections
- after Rule D2 re-entry calibration (`evaluate_round > 0`)

Write `drafting-progress.md: current_step: InDialogue` on every parent-managed entry into this step.

**Resume Detection** (run once on each `InDialogue` entry)

1. Read `section-progress.md` → `sections`, `reopen_reasons`; read `drafting-progress.md` → `current_step`.
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
   - if the user's reply contains a Reopen signal, stop the current section, rewrite it to `X`, clear the working buffer, and jump to **Reopen trigger**
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

**Reopen detection** — passive checkpoint

- do not proactively scan old `V` sections for consistency conflicts
- do not proactively ask whether a prior section should be reopened
- only react when the user explicitly includes a Reopen signal in the current or next reply

If the confirmation message itself includes a Reopen signal, process it immediately. Otherwise continue normally unless the user's next message includes a Reopen signal.

**Reopen trigger** (user-driven only)

Signal handling:
- explicit section id (`Reopen §3`, `§3 needs changes`) → trigger directly
- uniquely identifiable earlier section by description → restate the target section, then trigger after user confirmation
- vague earlier-section concern → ask which section should be reopened
- user-reported section conflict → restate the conflict and ask whether to reopen the earlier section; only trigger after explicit confirmation

When a valid Reopen targets an earlier section `§N`:

1. Write `sections[§N]: I` and record `reopen_reasons[§N] = <user reason>`.
2. Rewrite downstream confirmed sections to `!`:
   - between `§N+1` and the current section, rewrite any `V` or `D` section to `!`
   - after the current section, rewrite any `V` section to `!`
   - write each downstream `reopen_reasons[§M] = "reopened: §N — <§N section title>"`
3. Keep sections before `§N` unchanged.
4. Re-enter **Select Section**; `§N` re-enters through `I`-mode and downstream `!` sections are handled in order afterward.

Special case — Reopen the current `D` section itself:

1. Clear the current working buffer.
2. Rewrite `sections[§N]: X`.
3. Clear the current section body in `tech-doc.md`.
4. Do not propagate `!` to later sections.
5. Re-enter **Select Section** and rebuild the same section in `X`-mode.

This self-reopen path does not write `reopen_reasons` and does not change any other section state.

Reopen while outside `InDialogue`:

| Current step | Action |
|-------------|--------|
| `Extending` | Rewrite `drafting-progress.md: current_step: InDialogue`; discard any not-yet-registered custom section in the current round; then process Reopen. |
| `SkipConfirming` | Rewrite `drafting-progress.md: current_step: InDialogue`; restore the current unconfirmed `N/A-s` / `N/A-c` section to its pre-`S` state; then process Reopen. |
| `Checking` | Rewrite `drafting-progress.md: current_step: InDialogue`; discard the current checking result; then process Reopen. |

Exit condition:
- all standard sections and any registered custom sections are in `V`, `N/A-s`, or `N/A-c`
- no section remains in `I`, `X`, `D`, or `!`
- then write `drafting-progress.md: current_step: Extending`

#### Step 4 — Extending

Role: user-driven optional custom sections after all standard sections are resolved.

1. Prompt: standard sections are complete; the user may add a custom section or reply `完成`.
2. Loop:
   - `完成` → exit `Extending`, write `drafting-progress.md: current_step: SkipConfirming`, and continue to Step 5
   - custom section request with title + content structure:
     1. append the new section at the end of `tech-doc.md`
     2. register the new top-level custom section id as `§Cx: V` in `section-progress.md`
     3. run a one-time consistency check against existing `V` standard sections and report explicit conflicts only
     4. ask whether another custom section should be added

Custom sections have no template constraint: preserve the user-provided structure, formatting, and depth rather than forcing the standard template shape.

#### Step 5 — SkipConfirming

Process every section currently marked `N/A-s` or `N/A-c`, one section at a time:

1. Show the section id and title.
2. Show `na_evidence[§N]`.
3. Ask whether the user confirms the skip or wants to fill the section after all.

Per section:
- confirm skip → rewrite `sections[§N]: S`
- restore section → clear `na_evidence[§N]`, remove that section's leading N/A banner from `tech-doc.md`, and rewrite `sections[§N]: X`

Batch boundary rule:
- handle each N/A section immediately as `show → user choice → write state → next section`
- do not jump back to `InDialogue` mid-batch
- only after all current `N/A-s` / `N/A-c` sections are processed, if any were restored to `X`, rewrite `drafting-progress.md: current_step: InDialogue` once and re-enter `InDialogue` for the full batch of restored sections

Exit condition:
- every original `N/A-s` / `N/A-c` section is now either `S` or `X`
- no original N/A section remains unprocessed
- if none were restored to `X`, write `drafting-progress.md: current_step: Checking`

#### Step 6 — Checking

Write `drafting-progress.md: current_step: Checking` on entry and verify:

| Check | Pass condition |
|------|----------------|
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

#### Drafting Constraints

**Rule D3 — Code reads during drafting**

Read code files on demand (only what's relevant to the current design), never batch-load the entire codebase.

**Rule D4 — Output**

Write only `revision{N}/tech-doc.md`. It is the sole AI-generated artifact.

**Rule D5 — Skip evaluate to ReadyForDelivery**

User must explicitly request (e.g. "skip evaluation", "deliver without review"); if ambiguous, use AskQuestion.

Write `workflow-state.md`: `current_state: ReadyForDelivery`, `evaluate_round: 0`, `skip_evaluate_requested: true`; preserve `mode`, `product_ref`, `carry_forward_ref`. Then follow Rule R1.

### Evaluating Rules

<HARD-GATE>
Read `./eval-rules.md` before executing any evaluation step. Follow its instructions exactly.
</HARD-GATE>

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

## Session File Formats

Reference: `./formats.md` — read on demand when writing any session file.

---

## product → tech handoff

- `product_ref`: user-provided; never auto-detected; the two workflow directories are fully decoupled.
- `carry_forward_ref`: provided on re-entry; version delta between old tech-doc and new product-doc must be resolved via mandatory Drafting calibration.
- Re-entry = new iteration (new cycle_id or revision{N}); never continue in the old directory.

## Execution Mode: Apply

Read `$EXECUTION_MODE` from Session Foundation (set by parent `../_runtime.md`). Default: `guided`.

| Mode | Behavior |
|------|---------|
| `guided` | Current behavior — all rules apply as documented |
| `autonomous` | Apply the overrides below; all other rules unchanged |

### Autonomous Overrides

| Rule | Autonomous Behavior |
|------|-----------------------|
| `start` Phase 2 — run-mode detection | Auto-detect: if triggering message or session context includes a product-doc path → `product` mode; otherwise → `tech` mode. Do **not** ask. |
| Drafting Rule D2 — recalibrate on re-entry | Default Yes. Do **not** ask. |
| Drafting Rule D5 — skip evaluate to ReadyForDelivery | Default: proceed to Evaluating directly. Do **not** ask. User may explicitly request skip (e.g. "skip evaluation") to override. |
| Evaluating Rule E3 — per-issue AskQuestion | Default: Option A (Fix). Apply fix without asking. |
| ReadyForDelivery Rule R1 — delivery confirmation | **Feature container (autonomous):** auto-deliver — write `human-delivery-gate.md`, set `current_state: Delivered`, then auto handoff to `tech-work-order` (auto-chain). For topic containers or guided mode: unchanged (wait for explicit user confirmation). |
