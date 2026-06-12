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

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.
`$SESSION_CONTROL`, `$DRAFT_CONTROL`, `$ROUND_CONTROL`, or `$SESSION_INFO` non-zero exit → apply Blocking.

**Drafting — code reference** — Reference relevant source code for the current section; read narrowly, not the whole codebase.

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

**Evaluating fix resume → Step 4 — FreeEdit** (skip Steps 1–3).

Substep states: `Ready → RoundIteration → FreeEdit`.

#### Step 1 — Entry

Entry:
- **Evaluating fix resume** → Step 4 — FreeEdit
- **Otherwise** → dispatch Steps 2 → 3 in order

#### Step 2 — Initializing

1. Run `$DRAFT_CONTROL init-probe`. On failure → apply Blocking policy.
2. Dispatch — paste `init-probe` stdout verbatim under `## Input`:

```text
Load {actual $SKILL_ROOT}/tech-plan/initializing-runner/SKILL.md and follow its instructions.

## Input
{init-probe stdout}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`).

3. Run `$DRAFT_CONTROL init-complete`. On failure → apply Blocking policy.

#### Step 3 — Round Iteration Loop

Entry: Step 1 complete, or `drafting-progress.md: current_step: RoundIteration`.

On first entry after Step 1, run `$DRAFT_CONTROL begin-round`. On failure → apply Blocking policy.

Each round (Round N):

1. **Probe** — dispatch `prober-runner`:

```text
Load {actual $SKILL_ROOT}/tech-plan/prober-runner/SKILL.md and follow its instructions.

## Input
CYCLE_DIR:      {absolute path to $CACHE_DIR/<cycle_id>}
CYCLE_TYPE:     {feature | topic}
ROUND_N:        {N from `$DRAFT_CONTROL status`}
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
   - `commit-anchor` → `$ROUND_CONTROL append-anchor --section {X} --criterion "..." --round {N}`

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

3. **Round end** — when human confirms all items handled, run `$ROUND_CONTROL check-l0`.

If `l0_sections` is non-empty → block with message:
> 以下 section 仍为 L0，必须处理后才能进入下一轮：{section list}

4. **Skip ledger** — write non-L0 reject/skip entries: `$ROUND_CONTROL append-skip --section {X} --probe {P1} --round {N}`

5. **Convergence** — build flags from tracked round context (do not hardcode):

| Condition | Flag |
|---|---|
| No zoom accepted this round | `--no-accept` |
| Every initial ProbeReport failure was accept-resolved, reject/skip-recorded, or redirect-fixed; no open failures remain | `--probes-passed` |

Example when both hold: `$ROUND_CONTROL check-convergence --no-accept --probes-passed`

Omit `--probes-passed` when any probe failure was skipped/rejected without resolution. Omit `--no-accept` when any zoom was accepted.

- `converged: true` → present convergence summary (include state-vector from `$ROUND_CONTROL read-context`); ask:

> 1. Enter FreeEdit
> 2. Continue to the next round

  - **1** → `$DRAFT_CONTROL advance-to-freeedit`. On failure → apply Blocking policy. Then enter Step 4 - FreeEdit.
  - **2** → `$DRAFT_CONTROL advance-round`. On failure → apply Blocking policy. Return to step 1 (Probe).

- `converged: false` → `$DRAFT_CONTROL advance-round`. On failure → apply Blocking policy. Return to step 1 (Probe).

#### Step 4 — FreeEdit

Entry: `advance-to-freeedit` success, or Evaluating fix resume.

Rules:

- User drives edits; AI assists on request.
- When user signals done, ask: Evaluate or deliver directly?

- **Evaluate** → run `$SESSION_CONTROL start-evaluating`.
  > On failure → apply Blocking policy.
  > On success → follow **Evaluating Rules** below.

- **Deliver**
  run `$SESSION_CONTROL ready-for-delivery`.
  > On failure → apply Blocking policy.
  > On success → follow **ReadyForDelivery Rules** below.

### Evaluating Rules

Read `./eval-rules.md` and follow its instructions.

When eval-rules completes, follow its exit branch:

- **Deliver** → run `$SESSION_CONTROL ready-for-delivery`.
  > On failure → apply Blocking policy.
  > On success → follow **ReadyForDelivery Rules** below.

- **Continue editing** → enter **Step 4 — FreeEdit** (Evaluating fix resume; skip Steps 2–3).

### ReadyForDelivery Rules

1. Run `$SESSION_INFO delivery-preview`.

> On failure: apply Blocking policy.
> On success: show a delivery preview; full tech-doc only if asked.

2. Wait for explicit delivery confirmation.
3. Run `$SESSION_CONTROL deliver`.

> On failure: apply Blocking policy.
> On success: follow **Delivery Rules** below.

### Delivery Rules

1. Run `$SESSION_INFO stage-transitions`.

> On non-zero exit: apply Blocking policy.
> On success: prompt next stages when present.

---

## Command Index

Macro definitions referenced in the workflow above.

### `$SESSION_INFO`

`$SESSION_INFO <view>` →

```bash
python3 "$SKILL_DIR/scripts/session_info.py" --cycle-id "$CYCLE_ID" --view <view>
```

Views: `delivery-preview` · `session` · `stage-transitions` · `eval-summary`

### `$SESSION_CONTROL`

`$SESSION_CONTROL <subcommand>` →

```bash
python3 "$SKILL_DIR/scripts/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>
```

Subcommands: `start-evaluating` · `ready-for-delivery` · `deliver`

### `$DRAFT_CONTROL`

`$DRAFT_CONTROL <subcommand>` →

```bash
python3 "$SKILL_DIR/scripts/draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>
```

Subcommands: `init-probe` · `init-complete` · `begin-round` · `advance-round` · `advance-to-freeedit` · `status`

### `$ROUND_CONTROL`

`$ROUND_CONTROL <subcommand> [args...]` →

```bash
python3 "$SKILL_DIR/scripts/round_control.py" \
  --cycle-dir "$CACHE_DIR/$CYCLE_ID" <subcommand> [args...]
```

### `$FETCH_TECH_PLAN`

`$FETCH_TECH_PLAN <cycle_type> <role>` →

```bash
python3 "$SKILL_DIR/scripts/fetch_plan_framework.py" \
  --cycle-type <feature|topic> \
  --role <draft-template|draft-meta|eval-ptc|eval-tpef> \
  --project-root "$(pwd)"
```

Roles resolve to `workflow-config.json` keys via `fetch_plan_framework.py` (`FEATURE_ROLE_KEYS` / `TOPIC_ROLE_KEYS`).
On success: read stdout as framework markdown and announce `Template fetched: tech-plan.<resolved_key>`.
On failure: report error and stop current step. Cache path: `$CACHE_DIR/.template/tech-plan/<key>.md`.

---
