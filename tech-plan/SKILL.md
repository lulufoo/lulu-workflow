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

**Scope:** Tech document workflow only. Supports `run_mode` (`product` | `tech`) and `cycle_type` (`topic` architect | `feature` technical expert). Framework templates are shared; `cycle_type` selects role constraints via `$RESOLVE_PLAN_ROLE`.

<HARD-GATE name="Plan Scope Constraints">
Before Drafting or Evaluating work:

1. Run `$RESOLVE_PLAN_ROLE` (see Script Macros).
2. Read stdout as authoritative **Plan Scope Constraints**; apply `### Role`.
3. **Do not** select framework template URLs by `cycle_type` — fetch roles are shared across topic and feature.
</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>
- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

## Commands

### `start` — Session-level, run before each tech document

> Prerequisite: `init` has been run.

**Phase 1: Identify active cycle** — `_runtime.md` § Session Foundation. Do not run start.py until `$CYCLE_ID` is confirmed.

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

To resume an in-progress tech document, do not run start again — read `session-state.md` and `revision{N}/workflow-state.md`; use `$SESSION_INFO --view session` when needed.

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
6. Before writing session files, read schema contracts (SSOT):
   - `workflow-state.md` → `python3 "$SKILL_DIR/scripts/workflow_state_schema.py" --schema`
   - `evaluate-state.md` → `python3 "$SKILL_ROOT/eval/scripts/evaluate_state_schema.py" --schema`
   - `round-{N}/{section}/probe-{seq}.json` → `python3 "$SKILL_DIR/scripts/probe_report_schema.py" --schema` (version 3: section-gated probe SSOT)
   - `round-{N}/section-pointer.json` → `python3 "$SKILL_DIR/scripts/section_pointer_schema.py"` (via module; pointer SSOT)
   - `gap-report-round-{N}.json` → deprecated; use probe report above
   - `evaluate{M}/tech-review-*.md` → read `$SKILL_ROOT/eval/review.template.md`; run `python3 "$SKILL_ROOT/eval/scripts/review_schema.py" --schema`; read `$SKILL_ROOT/eval/SKILL.md` (Review table contract).

### Drafting Rules

**Entry:** fix resume → Step 3; otherwise Steps 1 → 2.
**Drafting states**: `Ready → RoundIteration → FreeEdit`.

#### Step 1 — Initializing

1. Run `$DRAFT_CONTROL begin-init`. 

- On failure → apply Blocking policy.
- On success → dispatch initializing-runner (stdout → `## Input`):

```text
Load {actual $SKILL_ROOT}/tech-plan/initializing-runner/SKILL.md and follow its instructions.

## Input
{begin-init stdout}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`).

2. Run `$DRAFT_CONTROL init-complete`. On failure → apply Blocking policy.

#### Step 2 — RoundIteration

- **Macro:** `begin-round` enters or resumes `RoundIteration`; `advance-round` increments macro N (stay in `RoundIteration`).
- **Per round N:** section-gated loop (2a–2d) — probe and decide **one `ACTIVE_SECTION` at a time** until every registry section is `stable`.

**Entry:** run `$DRAFT_CONTROL begin-round`.
- On failure → apply Blocking policy.
- On success → parse stdout JSON `round` as macro **N** for all `--round` args in this step.

##### Per round N

**Section loop** (for macro N) — after Entry `begin-round`, repeat **2a–2d** until every registry section is `stable`.

##### 2a. Probe active section

1. Run `$ROUND_PROBE_INPUT`; pin stdout as prober `## Input`. Includes `ACTIVE_SECTION`, `ROUND_DIR`, `ROUND_N`.
2. Dispatch prober-runner; await `$SUBAGENT_AWAIT_SYNC`.

##### 2b. Load report & present gaps

Load the latest probe report for  `ACTIVE_SECTION` only; render gap items and **wait** for user input.

`$ROUND_CONTROL read-probe-report --round {N}`.

- **KW0 gate:** if `kw0_pending_count` > 0 → show pending only; user edits tech-doc → return to **2a**.
- Render active-section `items` in two groups: **KW** (`gap_kind: kw`) then **Upstream** (`upstream_violation` / `upstream_coverage`).
- Footer: section statuses from pointer · `Undecided` · `KW0 pending` · `Upstream undecided` · `Probe seq`.
- Fix priority: KW undecided first, then upstream undecided.
- Prompt and **wait**: `Your call (Round {N} / {ACTIVE_SECTION})` — e.g. `{ACTIVE_SECTION}-1 accept`.
- **Rewind:** user requests upstream edit → `$ROUND_CONTROL rewind-section --round {N} --to {section}` → **2a**.

##### 2c. Human decide

**Gate:** Stop after 2b; proceed only on explicit user `{id} {accept|skip|redirect}` input — do not infer decisions.

Each decision → `$ROUND_CONTROL update-gap-decision --round {N} --id {id} --decision {accept|skip|redirect}`.

- `accept` → refiner dispatch
- `skip` / `redirect` → decision recorded only (skip also appends skip ledger)
- After refiner accept path → **2a** (re-probe same section).

Refiner input includes `ROUND_DIR`, `GAP_ITEM_ID`, `TECH_DOC_PATH`, `CYCLE_*`, `ROUND_N`.

##### 2d. Section advance

When `undecided_count` 0 and `kw0_pending_count` 0:

1. `$ROUND_CONTROL mark-section-stable --round {N} --section {ACTIVE_SECTION}`
2. `$ROUND_CONTROL advance-section --round {N}`

If not all stable → **2a** for new active section. If all stable → **2e**.

##### 2e. Round convergence

`$ROUND_CONTROL check-convergence --round {N} --no-accept --gaps-resolved`

- `converged: true` → FreeEdit or advance macro-round per user choice.
- `converged: false` → continue section loop, or run `$DRAFT_CONTROL advance-round` and re-parse stdout `round` as the new N.

#### Step 3 — FreeEdit

Entry: `advance-to-freeedit` success, or Evaluating fix resume.

Rules:

- User drives edits; AI assists on request.
- When user signals done, ask: Evaluate or deliver directly?

- **Evaluate** → follow **Evaluating Rules** below.

- **Deliver**
  run `$SESSION_CONTROL ready-for-delivery`.
  > On failure → apply Blocking policy.
  > On success → follow **ReadyForDelivery Rules** below.

### Evaluating Rules

Read `{$SKILL_ROOT}/eval/eval-rules.md` and follow its instructions.

eval-rules may loop Step 1–5 via **Re-evaluate** without exiting to parent.

When eval-rules completes, follow its exit branch:

- **Deliver** → run `$SESSION_CONTROL ready-for-delivery`.
  > On failure → apply Blocking policy.
  > On success → follow **ReadyForDelivery Rules** below.

- **Continue editing** → enter **Step 3 — FreeEdit** (Evaluating fix resume; skip Steps 1–2).

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

## Script Macros

Macros invoke `$SKILL_DIR/scripts/*.py`. Non-zero exit → Blocking (Principles).

| Macro | Command |
|-------|---------|
| `$SESSION_INFO` | `python3 "$SKILL_DIR/scripts/session_info.py" --cycle-id "$CYCLE_ID" --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_DIR/scripts/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$DRAFT_CONTROL` | `python3 "$SKILL_DIR/scripts/draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$DRAFT_CONTROL status` | `$DRAFT_CONTROL status` — stdout JSON: `current_step`, `round` |
| `$ROUND_CONTROL` | `python3 "$SKILL_DIR/scripts/round_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" <subcommand> [args...]` |
| `$ROUND_CONTROL init-round-dir` | `$ROUND_CONTROL init-round-dir --round {N}` |
| `$ROUND_CONTROL read-section-pointer` | `$ROUND_CONTROL read-section-pointer --round {N}` |
| `$ROUND_PROBE_INPUT` | `$ROUND_CONTROL round-probe-input` |
| `$ROUND_CONTROL advance-section` | `$ROUND_CONTROL advance-section --round {N}` |
| `$ROUND_CONTROL rewind-section` | `$ROUND_CONTROL rewind-section --round {N} --to {section_key}` |
| `$ROUND_CONTROL mark-section-stable` | `$ROUND_CONTROL mark-section-stable --round {N} --section {key}` |
| `$ROUND_CONTROL read-probe-report` | `$ROUND_CONTROL read-probe-report --round {N}` |
| `$ROUND_CONTROL read-upstream-context` | `$ROUND_CONTROL read-upstream-context --round {N}` |
| `$ROUND_CONTROL read-section-body` | `$ROUND_CONTROL read-section-body --section {key}` |
| `$ROUND_CONTROL update-gap-decision` | `$ROUND_CONTROL update-gap-decision --round {N} --id {id} --decision {accept\|skip\|redirect}` |
| `$ROUND_CONTROL check-convergence` | `$ROUND_CONTROL check-convergence --round {N} --no-accept --gaps-resolved` |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_DIR/scripts/plan_scope.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)"` |
| `$FETCH_TECH_PLAN` | `python3 "$SKILL_DIR/scripts/fetch_plan_framework.py" --role <role> --project-root "$(pwd)"` |

Subcommands and stdout: script module docstrings or `--help`.
