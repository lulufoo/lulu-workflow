---
name: tech-plan
description: >-
  Use when: 技术方案, 技术设计, tech design, tech-doc, 技术文档, 架构设计,
  技术规格, 技术实现方案, tech-doc workflow, 技术文档流程, 技术文档状态迁移,
  lulu-dev-workflow tech-plan, E2 E3 E4 评估, tech review, tech delivered.
disable-model-invocation: true
---

# tech-plan

> **Upstream (via `start`):** **tech mode** requires a delivered `tech-design` or `tech-diagnostic` scope doc.
> **product mode** requires a delivered `product-spec`. Initializing reads the scope snapshot from `workflow-state.delivered_refs`.

Drive a tech document workflow with explicit per-session state files and a hook
that gates state transitions.

**Scope:** Tech document workflow only. Supports `run_mode` (`product` | `tech`) and `cycle_type` (`feature`).

<HARD-GATE name="Plan Scope Constraints">
Before Drafting or Evaluating work:

1. Run `$RESOLVE_PLAN_ROLE`.
2. Read stdout as authoritative **Plan Scope Constraints**.

</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

</HARD-GATE>

<HARD-GATE name="Compose kernel macros">
Do NOT proceed until you have read `{SKILL_ROOT}/compose-kernel/SKILL.md` and loaded:

- `$FETCH_COMPOSE` from `## Script Macros`
- Fetch constraint: templates via `$FETCH_COMPOSE` only; do not read `workflow-config.json` directly

</HARD-GATE>

## Commands

### `start` — Session-level, run before each tech document

> Prerequisite: `init` has been run.

**Phase 1: Identify active cycle** — `_runtime.md` § Session Foundation. Do not run start.py until `$CYCLE_ID` is confirmed.

**Phase 2: Run start**

```bash
python3 "$SKILL_DIR/scripts/tech-plan_start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --profile tech-plan \
  --profile-path "$SKILL_DIR/compose-profile.json" \
  --run-mode product|tech \
  [--carry-forward-ref "<absolute-path-to-previous-tech-doc.md>"]  # optional
```

- Upstream documents are read from `{cycle_id}/delivered-refs.json` (written when prior stages **deliver**). `start.py` validates required entries via the profile StartAdapter, then snapshots them into `workflow-state.md` → `delivered_refs`.
- **product mode** requires a delivered `product-spec` entry; **tech mode** requires `tech-design` or `tech-diagnostic`.
- Initializing reads the snapshot from `workflow-state.delivered_refs` (not the file on disk).
- `--carry-forward-ref` is optional in both modes. Provide it when re-entering
  tech flow to use a previous tech-doc as the draft starting point.
- `--run-mode`: use `product` when product-spec context applies; otherwise `tech`.

> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.

To resume an in-progress tech document, do not run start again — run `$SESSION_INFO --view session`.

---

## product → tech handoff

- Upstream paths come from `delivered-refs.json` (each stage writes its compose doc on **deliver**); `start` snapshots into `workflow-state.delivered_refs`.
- `carry_forward_ref`: provided on re-entry; version delta between old tech-doc and new product-doc must be resolved via mandatory Drafting calibration.
- Re-entry = new iteration (new cycle_id or revision{N}); never continue in the old directory.

---

## State Model

Outer session transitions via `$SESSION_CONTROL` only (`compose-kernel/transitions/compose-session.json` — do not load directly).

---

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.
`$SESSION_CONTROL`, `$DRAFT_CONTROL`, or `$SESSION_INFO` non-zero exit → apply Blocking.

---

## Operating Rules

### General

1. Session reads: `$SESSION_INFO --view session` — `active_doc`, `workflow_state`; never infer state from tech-doc body or file existence.
2. State writes: `$SESSION_CONTROL` / `$DRAFT_CONTROL` only; during Evaluating follow eval-rules (do not Write cache state files directly).
3. Path guard blocks writes outside `$CACHE_DIR/` while a session is active.
4. Evaluating: follow `{$SKILL_ROOT}/eval/eval-rules.md` only.

### Drafting Rules

**Entry:** Evaluating fix resume → Step 2; otherwise Step 1.
**Drafting states**: `Ready → FreeEdit`.

#### Step 1 — Initializing

Compose draft from upstream scope doc (`design-doc` or `decision-doc`; `I*` / `F` / `C` per section; see initializing-runner Theory). No mapping paste.

1. Run `$DRAFT_CONTROL begin-init`. 

- On failure → apply Blocking.
- On success → dispatch initializing-runner (stdout → `## Input`):

```text
Load {actual $SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md and follow its instructions.

## Input
{begin-init stdout}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`).

2. Run `$DRAFT_CONTROL init-complete`. On failure → apply Blocking.

3. Run `$DRAFT_CONTROL advance-to-freeedit`. On failure → apply Blocking. Proceed to **Step 2 — FreeEdit**.

#### Step 2 — FreeEdit

Entry: `advance-to-freeedit` success, or Evaluating fix resume.

Rules:

- User drives edits; AI assists on request.
- When user signals done, ask: Evaluate or deliver directly?

- **Evaluate** → follow **Evaluating Rules** below.

- **Deliver** → **ReadyForDelivery Rules** below.

### Evaluating Rules

Read `{$SKILL_ROOT}/eval/eval-rules.md` and follow its instructions.

When eval-rules completes, follow its exit branch:

- **Deliver** → **ReadyForDelivery Rules** below.

- **Continue editing** → enter **Step 2 — FreeEdit** (Evaluating fix resume; skip Step 1).

### ReadyForDelivery Rules

1. Run `$SESSION_CONTROL ready-for-delivery`. On failure → Blocking.

2. Run `$SESSION_INFO --view delivery-preview`. On failure → Blocking. On success: show a delivery preview; full tech-doc only if asked.

3. Wait for explicit delivery confirmation.
4. Run `$SESSION_CONTROL deliver`. On failure → Blocking. On success → **Delivery Rules** below.

### Delivery Rules

1. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. On success: prompt next stages when present.

---

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md` | Step 1 — initializing-runner |
| `{$SKILL_ROOT}/eval/eval-rules.md` | Evaluating Rules |

---

## Script Macros

Macro expansion: `../_runtime.md` § Script Macros → Macro expansion. Non-zero exit → Blocking (Principles).

| Macro | Command |
|-------|---------|
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-plan --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-plan <subcommand>` |
| `$DRAFT_CONTROL` | `python3 "$SKILL_DIR/scripts/drafting/tech_plan_draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile tech-plan --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-plan` |
| `$EVAL_CONTROL` | `python3 "$SKILL_DIR/scripts/tech-plan_eval_control.py" --workflow tech-plan --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |

Subcommands and stdout: script module docstrings or `--help`.
