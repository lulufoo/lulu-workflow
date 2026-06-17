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
python3 "$SKILL_ROOT/compose-kernel/scripts/core/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --profile tech-plan \
  --run-mode product|tech \
  [--product-ref "<absolute-path-to-product-doc.md>"]  # required for product mode
  [--carry-forward-ref "<absolute-path-to-previous-tech-doc.md>"]  # optional
  [--design-ref "<absolute-path-to-design-doc.md>"]  # optional supplementary context
```

- `--carry-forward-ref` is optional in both modes. Provide it when re-entering
  tech flow to use a previous tech-doc as the draft starting point.
- `--run-mode`: use `product` if a `product-doc.md` path was provided (user-supplied, do not auto-detect), otherwise `tech`.

> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

To resume an in-progress tech document, do not run start again — run `$SESSION_INFO --view session`.

---

## product → tech handoff

- `product_ref`: user-provided; never auto-detected; the two workflow directories are fully decoupled.
- `carry_forward_ref`: provided on re-entry; version delta between old tech-doc and new product-doc must be resolved via mandatory Drafting calibration.
- Re-entry = new iteration (new cycle_id or revision{N}); never continue in the old directory.

---

## State Model

State transitions via `$SESSION_CONTROL` / `$EVAL_CONTROL`; `transition-whitelist.json` enforced by control scripts and hook — do not load it directly.

---

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.
`$SESSION_CONTROL`, `$DRAFT_CONTROL`, `$ROUND_CONTROL`, or `$SESSION_INFO` non-zero exit → apply Blocking.

**Drafting — code reference** — Reference relevant source code for the current section; read narrowly, not the whole codebase.

---

## Operating Rules

### General

1. Session reads: `$SESSION_INFO --view session` — `active_doc`, `workflow_state`; never infer state from tech-doc body or file existence.
2. Config/templates: `$FETCH_TECH_PLAN <role>` on demand; do not read `workflow-config.json` directly. Roles: `section-registry`, `outline-registry`, `feature-role-instance`, `feature-domain-instance`, `section-kw-criteria`, `intent-eval-framework`, `eval-ptc`.
3. State writes: `$SESSION_CONTROL` / `$DRAFT_CONTROL` / `$ROUND_CONTROL` / `$EVAL_CONTROL` only; do not Write cache data files directly.
4. Path guard blocks writes outside `$CACHE_DIR/` while a session is active.
5. Evaluating review contract: `{$SKILL_ROOT}/eval/eval-rules.md` and `{$SKILL_ROOT}/eval/SKILL.md` (probe/remediation runners own `review.template.md`).

### Drafting Rules

**Entry:** fix resume → Step 3; otherwise Steps 1 → 2.
**Drafting states**: `Ready → RoundIteration → FreeEdit`.

#### Step 1 — Initializing

Compose draft from decision-doc (`I*` / `F` / `C` per section; see initializing-runner Theory). No mapping paste.

1. Run `$DRAFT_CONTROL begin-init`. 

- On failure → apply Blocking policy.
- On success → dispatch initializing-runner (stdout → `## Input`):

```text
Load {actual $SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md and follow its instructions.

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

Repeat **2a–2d** until every registry section is `stable`.

##### 2a. Probe active section

1. Run `$ROUND_CONTROL round-probe-input`; pin stdout as prober `## Input`. Includes `ACTIVE_SECTION`, `ROUND_DIR`, `ROUND_N`.
2. Dispatch prober-runner (stdout → `## Input`):

```text
Load {actual $SKILL_ROOT}/compose-kernel/runners/prober-runner/SKILL.md and follow its instructions.

## Input
{round-probe-input stdout}
```

Await `$SUBAGENT_AWAIT_SYNC`.

##### 2b. Present gaps

1. `$ROUND_CONTROL read-probe-report --round {N}` — pin stdout as **`$PROBE`**.
2. `$ROUND_CONTROL read-section-pointer --round {N}` — pin stdout as **`$POINTER`**.
3. Read `{SKILL_ROOT}/compose-kernel/references/gap-display.md`; render user copy from **`$PROBE` + `$POINTER` only** (do not read probe files on disk).

- **KW0 gate:** `$PROBE.kw0_pending_count` > 0 → pending rows only (gap-display pipeline step 1); user edits tech-doc → **2a** (skip 2c).
- **Rewind:** upstream edit → `$ROUND_CONTROL rewind-section --round {N} --to {section}` → **2a**.

##### 2c. Human decide

**Gate:** After 2b presentation and wait (gap-display template footer); proceed only on explicit `{id} {accept|skip|redirect}` — do not infer.

Each decision → `$ROUND_CONTROL update-gap-decision --round {N} --id {id} --decision {accept|skip|redirect}`.

- `accept` → refiner dispatch (`$ROUND_CONTROL read-gap-item` for payload):

```text
Load {actual $SKILL_ROOT}/compose-kernel/runners/refiner-runner/SKILL.md and follow its instructions.

## Input
{read-gap-item stdout}
```

Await `$SUBAGENT_AWAIT_SYNC`.
- `skip` / `redirect` → decision recorded only (skip also appends skip ledger)
- After refiner accept path → **2a** (re-probe same section).

Refiner input includes `ROUND_DIR`, `GAP_ITEM_ID`, `TECH_DOC_PATH`, `CYCLE_*`, `ROUND_N`.

##### 2d. Section advance

When `$PROBE.undecided_count` 0 and `$PROBE.kw0_pending_count` 0 (after 2b presentation):

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

1. Run `$SESSION_INFO --view delivery-preview`.

> On failure: apply Blocking policy.
> On success: show a delivery preview; full tech-doc only if asked.

2. Wait for explicit delivery confirmation.
3. Run `$SESSION_CONTROL deliver`.

> On failure: apply Blocking policy.
> On success: follow **Delivery Rules** below.

### Delivery Rules

1. Run `$SESSION_INFO --view stage-transitions`.

> On non-zero exit: apply Blocking policy.
> On success: prompt next stages when present.

---

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose-kernel/references/gap-display.md` | Round Iteration **2b** step 3 — render from pinned `$PROBE` + `$POINTER` (parent runs steps 1–2) |
| `{$SKILL_ROOT}/eval/eval-rules.md` | Evaluating Rules |

---

## Script Macros

Macro expansion: `../_runtime.md` § Script Macros → Macro expansion.

Macros invoke compose-kernel scripts (`$SKILL_ROOT/compose-kernel/scripts/...`) or shell scripts (`$SKILL_DIR/scripts/...` for `$DRAFT_CONTROL` only). Non-zero exit → Blocking (Principles).

| Macro | Command |
|-------|---------|
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$DRAFT_CONTROL` | `python3 "$SKILL_DIR/scripts/draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$DRAFT_CONTROL status` | `$DRAFT_CONTROL status` — stdout JSON: `current_step`, `round` |
| `$ROUND_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/section_round_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" <subcommand> [args...]` |
| `$ROUND_CONTROL init-round-dir` | `$ROUND_CONTROL init-round-dir --round {N}` |
| `$ROUND_CONTROL read-section-pointer` | `$ROUND_CONTROL read-section-pointer --round {N}` |
| `$ROUND_CONTROL advance-section` | `$ROUND_CONTROL advance-section --round {N}` |
| `$ROUND_CONTROL rewind-section` | `$ROUND_CONTROL rewind-section --round {N} --to {section_key}` |
| `$ROUND_CONTROL mark-section-stable` | `$ROUND_CONTROL mark-section-stable --round {N} --section {key}` |
| `$ROUND_CONTROL read-probe-report` | `$ROUND_CONTROL read-probe-report --round {N}` |
| `$ROUND_CONTROL read-upstream-context` | `$ROUND_CONTROL read-upstream-context --round {N}` |
| `$ROUND_CONTROL read-section-body` | `$ROUND_CONTROL read-section-body --section {key}` |
| `$ROUND_CONTROL update-gap-decision` | `$ROUND_CONTROL update-gap-decision --round {N} --id {id} --decision {accept\|skip\|redirect}` |
| `$ROUND_CONTROL check-convergence` | `$ROUND_CONTROL check-convergence --round {N} --no-accept --gaps-resolved` |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-domain --cycle-id "$CYCLE_ID" --project-root "$(pwd)"` |
| `$FETCH_TECH_PLAN` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_plan_framework.py" --role <role> --project-root "$(pwd)"` |
| `$SECTION_INTENT` | `python3 "$SKILL_ROOT/compose-kernel/scripts/schema/section/registry/section_registry_schema.py" --section-intent {key} --project-root "$(pwd)"` |
| `$SECTION_INTENT_BOUNDARY` | `python3 "$SKILL_ROOT/compose-kernel/scripts/schema/section/registry/section_registry_schema.py" --section-intent-boundary {key} --project-root "$(pwd)"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/eval/scripts/eval_control.py" --workflow tech-plan --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` — subcommands: `{$SKILL_ROOT}/eval/eval-rules.md` and `{$SKILL_ROOT}/eval/SKILL.md` |

Subcommands and stdout: script module docstrings or `--help`.
