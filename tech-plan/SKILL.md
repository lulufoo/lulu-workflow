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
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

**This workflow runs in Agent mode with path guard.**

## Commands


### `start` — Session-level, run before each tech document

> Prerequisite: `init` has been run.

**Step 1: Identify active cycle** — See `## Session Foundation` in `../SKILL.md`

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Step 2: Determine run-mode**

If the user has not provided a `product-doc.md` path, ask:

> "Is this a pure tech task (no product-doc)? Or do you have a product-doc.md?"

| User answer | run-mode | --product-ref |
|-------------|----------|---------------|
| Pure tech, no product-doc | `tech` | omit |
| Has product-doc | `product` | absolute path (user-provided) |

Do not infer or auto-detect the path.

**Step 3: Run start**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --run-mode product|tech \
  [--product-ref "<absolute-path-to-product-doc.md>"]  # required for product mode
  [--carry-forward-ref "<absolute-path-to-previous-tech-doc.md>"]  # optional
```

`--carry-forward-ref` is optional in both modes. Provide it when re-entering
tech flow to use a previous tech-doc as the draft starting point.
> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

---

## Session File Structure

```
$CACHE_DIR/<cycle_id>/tech/plan/
  session-state.md               ← active_doc: N (monotonically increasing)

  revision{N}/                          ← Nth tech doc
    workflow-state.md            ← current_state, evaluate_round (AI writes; hook validates)
    tech-doc.md                  ← sole AI-generated artifact
    evaluate-state.md            ← evaluation progress
    human-delivery-gate.md       ← delivery gate

    evaluate{M}/                 ← Mth evaluation round (monotonically increasing)
      tech-review-e{M}1.md       ← E1: intent alignment review
      tech-review-e{M}2.md       ← E2: codebase consistency review
      tech-review-e{M}3.md       ← E3: solution quality review
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

1. Read `$WORKFLOW_DIR/workflow-config.json` → `tech` section before driving the workflow.
2. Read `session-state.md` → `active_doc: N` to determine current document round.
3. `revision{N}/workflow-state.md` is the authoritative current state — write it to request a transition.
4. Never infer state from document body or file existence; always read `workflow-state.md`.
5. Use full `Write` (not `Edit`) for `workflow-state.md` and `evaluate-state.md`.
6. This workflow runs in Agent mode. Writes outside `$CACHE_DIR/`
   are blocked by the path guard hook while a session is active.

### Drafting Rules

**Rule D1 — Calibration routing on entry**

Read `workflow-state.md` → `evaluate_round` to determine entry path:

| Condition | Calibration | Required reads |
|-----------|-------------|----------------|
| `evaluate_round == 0`, `carry_forward_ref` empty | Mandatory (full) | product-doc.md + `ac_url` (if set) + `tpt_url` (feature) or `shaping_tpt_url` (topic) |
| `evaluate_round == 0`, `carry_forward_ref` present | Mandatory (diff) | carry_forward tech-doc.md + product-doc.md + `ac_url` (if set) |
| `evaluate_round > 0` (return from Evaluating) | Present `fix_severity` from evaluate-state.md; user decides | Per user choice (see D2) |

**Rule D2 — Re-entry calibration (evaluate_round > 0)**

Show the user: `"Fix severity this round: [fix_severity] — [fix_severity_reason]. Recalibrate?"`

| User choice | Action |
|-------------|--------|
| Yes | Read `ac_url` + `tpt_url` (feature) or `shaping_tpt_url` (topic) + product-doc relevant sections (if E1 issues last round) + code files (if E2 issues last round) |
| Skip | Proceed directly to writing |

**Rule D3 — Code reads during drafting**

Read code files on demand (only what's relevant to the current design), never batch-load the entire codebase.

**Rule D4 — Output**

Write only `revision{N}/tech-doc.md`. It is the sole AI-generated artifact.

**Rule D5 — Skip evaluate to ReadyForDelivery**

User must explicitly request (e.g. "skip evaluation", "deliver without review"); if ambiguous, use AskQuestion.

Write `workflow-state.md`: `current_state: ReadyForDelivery`, `evaluate_round: 0`, `skip_evaluate_requested: true`; preserve `mode`, `product_ref`, `carry_forward_ref`. Then follow Rule R1.

### Evaluating Rules

**Rule E1 — Entry sequence**

On entering Evaluating:
1. Increment `evaluate_round` in `workflow-state.md` (write `current_state: Evaluating, evaluate_round: M`)
2. Read `mode` from `workflow-state.md` to determine evaluation path
3. Initialize `evaluate-state.md` based on mode:

```
# product mode: current_dimension: e1, e1_status: pending
# tech mode: current_dimension: e2, e1_status: complete (preset), e1_total_issues: 0, e1_resolved_issues: 0
current_dimension: e1|e2
e1_status: pending|complete
e2_status: pending, e3_status: pending
total_issues: 0, resolved_issues: 0
fix_severity: "", fix_severity_reason: ""
```

**Rule E2 — Dimension sequencing**

| Mode | Sequence | Skip | E1 file | E2 file | E3 file |
|------|---------|------|---------|---------|---------|
| product | E1 → E2 → E3 | none | `tech-review-e{M}1.md` | `tech-review-e{M}2.md` | `tech-review-e{M}3.md` |
| tech | E2 → E3 | E1 (preset complete) | — | `tech-review-e{M}2.md` | `tech-review-e{M}3.md` |

Inputs per dimension: E1 ← product_ref + `ptc_url`; E2 ← relevant code files; E3 ← `tpef_url` (feature) or `shaping_tpef_url` (topic).

Do not skip within the required sequence.

**Rule E3 — Per-dimension sequence**

For each dimension (example: E1):
1. Write `e1_status: in_progress`, `current_dimension: e1` to `evaluate-state.md`
2. Load inputs (see E2 table)
3. Write `evaluate{M}/tech-review-e{M}1.md` skeleton (issues list)
4. Write `e1_total_issues: K`, update `total_issues = e1_total + e2_total + e3_total`
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
- Option A: Confirm, fix the issue
- Option B: Ignore, no impact on delivery

**Rule E6 — Abandon evaluation**

User must explicitly request; if ambiguous, use AskQuestion. Steps are order-strict:

1. **Write** `evaluate-state.md`: set `current_dimension: abandoned`, preserve all other fields.
2. **Write** `workflow-state.md`: `current_state: Drafting`, `evaluate_round: M` (unchanged, next Evaluating entry increments to M+1), `skip_evaluate_requested: false`; preserve `mode`, `product_ref`, `carry_forward_ref`.

Hook validates `current_dimension: abandoned` before allowing the transition. `evaluate{M}/` and review files are retained as history.

### ReadyForDelivery Rules

**Rule R1 — Delivery confirmation**

After hook allows entry to ReadyForDelivery:
1. Present final `revision{N}/tech-doc.md` to user
2. Wait for explicit delivery confirmation
3. Write `revision{N}/human-delivery-gate.md`
4. Write `revision{N}/workflow-state.md` → `current_state: Delivered`

---

## Session File Formats

### revision{N}/workflow-state.md

```markdown
---
version: 1
workflow: tech-doc
mode: product
current_state: Drafting
evaluate_round: 0
skip_evaluate_requested: false
product_ref: /abs/path/$CACHE_DIR/<cycle_id>/product/plan/revision1/product-doc.md
carry_forward_ref: ""
updated_at: 2026-05-17T09:00:00+08:00
---
```

> `mode`: set by `start.py`; preserve on every manual write of `workflow-state.md`.
> `skip_evaluate_requested: true`: only for `Drafting → ReadyForDelivery`; omit when writing `Delivered`.

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
# {E1|E2|E3} Review: {Intent Alignment|Codebase Consistency|Solution Quality} — revision{N} round {M}

**Date:** YYYY-MM-DD
**Refs:** [E1: product_ref + ptc_url / E2: relevant code paths / E3: tpef_url]

| # | Issue | [E2: file] | [E3: dimension] | Severity | Status | Decision |
|---|-------|-----------|-----------------|----------|--------|---------|
| {E1|E2|E3}-1 | ... | ... | critical/medium/minor | ✅ Fixed | fix |
```

---

## product → tech handoff

- `product_ref`: user-provided; never auto-detected; the two workflow directories are fully decoupled.
- `carry_forward_ref`: provided on re-entry; version delta between old tech-doc and new product-doc must be resolved via mandatory Drafting calibration.
- Re-entry = new iteration (new cycle_id or revision{N}); never continue in the old directory.

## Execution Mode: Apply

Read `$EXECUTION_MODE` from Session Foundation (set by parent `SKILL.md`). Default: `guided`.

| Mode | Behavior |
|------|---------|
| `guided` | Current behavior — all rules apply as documented |
| `autonomous` | Apply the overrides below; all other rules unchanged |

### Autonomous Overrides

| Rule | Autonomous Behavior |
|------|-----------------------|
| `start` Step 2 — run-mode detection | Auto-detect: if triggering message or session context includes a product-doc path → `product` mode; otherwise → `tech` mode. Do **not** ask. |
| Drafting Rule D2 — recalibrate on re-entry | Default Yes. Do **not** ask. |
| Drafting Rule D5 — skip evaluate to ReadyForDelivery | Default: proceed to Evaluating directly. Do **not** ask. User may explicitly request skip (e.g. "skip evaluation") to override. |
| Evaluating Rule E3 — per-issue AskQuestion | Default: Option A (Fix). Apply fix without asking. |
| ReadyForDelivery Rule R1 — delivery confirmation | **Feature container (autonomous):** auto-deliver — write `human-delivery-gate.md`, set `current_state: Delivered`, then auto handoff to `tech-work-order` (auto-chain). For topic containers or guided mode: unchanged (wait for explicit user confirmation). |
