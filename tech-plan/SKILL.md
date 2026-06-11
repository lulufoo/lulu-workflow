---
name: tech-plan
description: >-
  Use when: 技术方案, 技术设计, tech design, tech-doc, 技术文档, 架构设计,
  技术规格, 技术实现方案, tech-doc workflow, 技术文档流程, 技术文档状态迁移,
  lulu-dev-workflow tech-plan, E1 E2 E3 评估, Round Iteration, tech review, tech delivered.
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

1. Substep states: `Ready → Initializing → L1Scaffold → RoundIteration → FreeEdit`
2. Substep state is recorded in `drafting-progress.md`.

#### Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason (stderr, exit code), and **wait** for user direction before continuing.

Any `round_state.py` non-zero exit → apply Blocking policy.

#### Step 0 — Entry

Read `workflow-state.md` → `evaluate_round`, `mode`, `carry_forward_ref`.

**If `evaluate_round > 0`:** read `evaluate-state.md` → `fix_severity`, `fix_severity_reason`; present to the user:

> "上轮评估结果：[fix_severity] — [fix_severity_reason]。"

Resolve drafting template keys from cycle type (sub-agents fetch via `$FETCH_TEMPLATE`):

- feature → template: `tech-plan` / `tpt_v2_url`；meta: `tech-plan` / `tpt_meta_v2_url`
- topic → template: `tech-plan` / `shaping_tpt_url`；meta: `tech-plan` / `tpt_meta_url`

Use:
- `Use $FETCH_TEMPLATE tech-plan <key>`
- Read stdout as template body; on failure report error and stop current step.

Then dispatch Steps 1 → 3 → 3.5 in order. If returning from Evaluating fix, enter Step 4 directly.

#### Step 1 — Initializing

Entry condition: `drafting-progress.md: current_step: Ready` (or file absent).
Exit condition: subagent writes `drafting-progress.md: current_step: L1Scaffold`.

Dispatch:

```text
Load {actual $SKILL_ROOT}/tech-plan/initializing-runner/SKILL.md and follow its instructions.

## Input
REVISION_DIR:         {absolute path to revision{N}/}
DECISION_DOC_PATH:    {absolute path to decision-doc.md}
CYCLE_TYPE:           {feature | topic}
CYCLE_ID:             {cycle_id}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`); verify `drafting-progress.md: current_step: L1Scaffold`.

#### Step 3 — L1Scaffold

Entry condition: `drafting-progress.md: current_step: L1Scaffold`.
Exit condition: `drafting-progress.md: current_step: RoundIteration`.

Write `drafting-progress.md` with:

```yaml
---
version: 1
cycle_id: {cycle_id}
current_step: RoundIteration
round: 1
---
```

Then enter Step 3.5.

#### Step 3.5 — Round Iteration Loop

Entry condition: `drafting-progress.md: current_step: RoundIteration`.

Each round (Round N):

1. **Probe** — dispatch `prober-runner`:

```text
Load {actual $SKILL_ROOT}/tech-plan/prober-runner/SKILL.md and follow its instructions.

## Input
CYCLE_DIR:      {absolute path to $CACHE_DIR/<cycle_id>}
CYCLE_TYPE:     {feature | topic}
ROUND_N:        {N from drafting-progress.md}
TECH_DOC_PATH:  {absolute path to revision{N}/tech-doc.md}
```

Pin ProbeReport at top of conversation; keep visible for the entire round.

Track round context throughout step 2 (reset at start of each round):

- `round_had_accept`: `true` if any zoom was accepted this round
- `round_probe_failures`: count of ProbeReport lines that are not `无问题` at round start (before human decisions)

2. **Human decide** — for each ProbeReport item:
   - `accept` → dispatch `refiner-runner` (ProbeReport stays pinned)
   - `reject` / `skip` → mark as ignored this round (ProbeReport stays pinned)
   - `redirect` → human edits `tech-doc.md` directly (ProbeReport stays pinned)
   - `commit-anchor` → append anchor:

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  append-anchor --section {X} --criterion "..." --round {N}
```

Refiner dispatch (per accept):

```text
Load {actual $SKILL_ROOT}/tech-plan/refiner-runner/SKILL.md and follow its instructions.

## Input
CYCLE_DIR:       {absolute path to $CACHE_DIR/<cycle_id>}
CYCLE_TYPE:      {feature | topic}
SECTION:         {section key or name}
CURRENT_L:       {current L}
TARGET_L:        {target L}
ROUND_N:         {N}
TECH_DOC_PATH:   {absolute path to revision{N}/tech-doc.md}
ZOOM_EVIDENCE:   {probe failure evidence}
```

3. **Round end** — when human confirms all items handled, run L0 block check:

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  check-l0
```

If `l0_sections` is non-empty → block with message:
> 以下 section 仍为 L0，必须处理后才能进入下一轮：{section list}

4. **Skip ledger** — write non-L0 reject/skip entries:

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  append-skip --section {X} --probe {P1} --round {N}
```

5. **Convergence** — build flags from tracked round context (do not hardcode):

| Condition | Flag |
|---|---|
| No zoom accepted this round | `--no-accept` |
| Every initial ProbeReport failure was accept-resolved, reject/skip-recorded, or redirect-fixed; no open failures remain | `--probes-passed` |

Example when both hold:

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  check-convergence --no-accept --probes-passed
```

Omit `--probes-passed` when any probe failure was skipped/rejected without resolution. Omit `--no-accept` when any zoom was accepted.

- `converged: true` → advance:

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" \
  advance-to-freeedit
```

Then enter Step 4.

- `converged: false` → increment `round` in `drafting-progress.md` → return to step 1.

Exit condition: `drafting-progress.md: current_step: FreeEdit`.

#### Step 4 — FreeEdit

Entry paths:

- after Step 3.5 — Round Iteration converges
- after Evaluating returns fix to Drafting (resume directly here; skip Steps 1–3.5)

Rules:

- User drives edits; AI assists on request.
- On user "完成", ask:

> "Start evaluation, or deliver directly?"

- **Evaluate** → write `workflow-state.md` → `current_state: Evaluating`.
- **Deliver directly** → run:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-id "<cycle_id>" \
  --project-root "$(pwd)" \
  ready-for-delivery
```

> On non-zero exit: apply Blocking policy.
> On success: follow **ReadyForDelivery Rules** below.

### Evaluating Rules

Read `./eval-rules.md` and follow its instructions.

When eval-rules completes Phase 4, run:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-id "<cycle_id>" \
  --project-root "$(pwd)" \
  ready-for-delivery
```

> On non-zero exit: apply Blocking policy.
> On success: follow **ReadyForDelivery Rules** below.

### ReadyForDelivery Rules

Entry: `current_state` is `ReadyForDelivery`.

1. Run:

```bash
python3 "$SKILL_DIR/scripts/session_info.py" \
  --cycle-id "<cycle_id>" \
  --project-root "$(pwd)" \
  --view delivery-preview
```

> On non-zero exit: apply Blocking policy.
> On success: show a delivery preview; full tech-doc only if asked.

2. Wait for explicit delivery confirmation.
3. Run:

```bash
python3 "$SKILL_DIR/scripts/session_control.py" \
  --cycle-id "<cycle_id>" \
  --project-root "$(pwd)" \
  deliver
```

> On non-zero exit: apply Blocking policy.
> On success: follow **Delivery Rules** below.

### Delivery Rules

1. Run:

```bash
python3 "$SKILL_DIR/scripts/session_info.py" \
  --cycle-id "<cycle_id>" \
  --project-root "$(pwd)" \
  --view stage-transitions
```

> On non-zero exit: apply Blocking policy.
> On success: prompt next stages when present.

---
