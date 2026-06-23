---
name: product-spec
description: >-
  Use when: 产品规格, feature PRD, product spec, product-doc,
  lulu-dev-workflow product-spec, product delivered, 产品文档.
disable-model-invocation: true
---

# product-spec

> **Prerequisite:** Delivered `decision-doc` from `product-diagnostic`.
> **Phase 2 (MVP):** Initializing + Evaluating + Delivery. Round Iteration / FreeEdit are **deferred** — do not run them unless explicitly re-enabled.

Produce **product-doc.md** — feature product specification for human sign-off before `tech-diagnostic`.

**Scope:** Feature cycle only. Topic/shaping cycles are out of scope (future `product-arch`).

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/product-spec`

</HARD-GATE>

<HARD-GATE name="Compose kernel macros">
Do NOT proceed until you have read `{SKILL_ROOT}/compose-kernel/SKILL.md` and loaded:

- `$FETCH_COMPOSE` (always pass `--profile product-spec`)
- Fetch constraint: templates via `$FETCH_COMPOSE` only; do not read `workflow-config.json` directly

</HARD-GATE>

<HARD-GATE name="Plan Scope Constraints">
Before product drafting or evaluation:

1. Run `$RESOLVE_PLAN_ROLE`.
2. Read stdout as authoritative **Plan Scope Constraints** (domain + role).

</HARD-GATE>

## Commands

### `start` — Session-level, run before each product document

> Prerequisite: product-diagnostic `decision-doc` Delivered for this feature cycle.

**Phase 1:** Identify active cycle — `_runtime.md` § Session Foundation. Do not run start.py until `$CYCLE_ID` is confirmed.

**Phase 2:** Run start

```bash
python3 "$SKILL_DIR/scripts/product-spec_start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --profile product-spec \
  --profile-path "$SKILL_DIR/compose-profile.json" \
  --run-mode product
```

- Requires `product-diagnostic` in `{cycle_id}/delivered-refs.json` (written when product-diagnostic **delivers**). `start.py` snapshots it into `workflow-state.delivered_refs`; Initializing reads the snapshot.
- Topic cycles are rejected at start with explicit stderr.

To resume an in-progress product document, do not run start again — run `$SESSION_INFO --view session`.

---

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.

**Drafting — decision-doc first** — Ground product intent in the delivered decision-doc; do not invent scope beyond verified diagnostic conclusions.

---

## Drafting Rules

**Entry:** Step 1 — Initializing only, or resume via `$SESSION_INFO --view session`.
**Drafting state (MVP):** `Ready` after `init-complete`. Do **not** enter RoundIteration or FreeEdit.

**After Initializing completes:** present summary; user may enter **Evaluating** or **Deliver** only.

#### Step 1 — Initializing

Compose product-doc from decision-doc (`I*` / `F` / `C` per section; see initializing-runner Theory). No mapping paste.

1. Run `$DRAFT_CONTROL begin-init`.
   - On failure → Blocking.
   - On success → dispatch initializing-runner (stdout → `## Input`):

```text
Load {actual $SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md and follow its instructions.

## Input
{begin-init stdout}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`).

2. Run `$DRAFT_CONTROL init-complete`. On failure → Blocking.

3. **Pause gate:** Present runner return summary and `product-doc.md` path. Ask: Evaluate, or Deliver?

> **Out of scope (deferred):** Round Iteration (`begin-round`, `$ROUND_CONTROL`, prober/refiner) and FreeEdit. If the user asks to refine by section, use direct edits on `product-doc.md` and re-run `init-complete` validation only when re-seeding from scratch — do not invoke round macros.

### Evaluating Rules

Read `{$SKILL_ROOT}/eval/eval-rules.md` and follow its instructions (only when user explicitly chooses Evaluate).

When eval-rules completes, follow its exit branch:

- **Deliver** → **ReadyForDelivery Rules** below.

**Evaluating (feature):** Independent **PDQA** on `product-doc.md` — not compose Round/probe iteration.

Load rubric via `pst_product_eval_framework_url` → legacy [`12-product-doc-evaluation-framework.md`](https://github.com/lulufoo/lulu-workflow-framework/blob/main/lulu-dev-workflow/template/product-plan/12-product-doc-evaluation-framework.md) (11 dimensions, 4 layers).

| Dim | Id | Focus |
|-----|-----|-------|
| pdqa | `product-doc-quality` | Holistic product-doc quality audit per PDQA framework |

### ReadyForDelivery Rules

1. Run `$SESSION_CONTROL ready-for-delivery`. On failure → Blocking.

2. Run `$SESSION_INFO --view delivery-preview`. On failure → Blocking. On success: show a delivery preview; full product-doc only if asked.

3. Wait for explicit delivery confirmation.

4. Run `$SESSION_CONTROL deliver`. On failure → Blocking. On success → **Delivery Rules** below.

### Delivery Rules

1. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. On success: prompt next stages when present.

---

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md` | Step 1 — Initializing |
| `{$SKILL_ROOT}/eval/eval-rules.md` | Evaluating (user-initiated) |

Template SSOT: [product-spec templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/product-spec)

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile product-spec --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile product-spec <subcommand>` |
| `{SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md` | Step 1 — initializing-runner |
| `$DRAFT_CONTROL` | `python3 "$SKILL_DIR/scripts/drafting/product_spec_draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` — MVP: `begin-init`, `init-complete`, `status` only |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile product-spec` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile product-spec --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_DIR/scripts/product-spec_eval_control.py" --workflow product-spec --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |

Subcommands and stdout: script module docstrings or `--help`.
