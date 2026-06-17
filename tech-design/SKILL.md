---
name: tech-design
description: >-
  Use when: 技术方案设计, tech design stage, design-doc,
  lulu-dev-workflow tech-design, design delivered, 设计文档.
disable-model-invocation: true
---

# tech-design

> **Prerequisite:** Delivered `decision-doc` from `tech-diagnostic`.
> **Phase 2:** Full Drafting lifecycle (Initializing → Round → FreeEdit) + Evaluating + Delivery wired.

Produce **design-doc.md** — technical solution design for human sign-off before `tech-plan`.

**Scope:** Feature cycle only.

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
- `$SKILL_DIR` = `$SKILL_ROOT/tech-design`

</HARD-GATE>

<HARD-GATE name="Compose kernel macros">
Do NOT proceed until you have read `{SKILL_ROOT}/compose-kernel/SKILL.md` and loaded:

- `$FETCH_COMPOSE` (always pass `--profile tech-design`)
- Fetch constraint: templates via `$FETCH_COMPOSE` only; do not read `workflow-config.json` directly

</HARD-GATE>

<HARD-GATE name="Plan Scope Constraints">
Before design drafting or evaluation:

1. Run `$RESOLVE_PLAN_ROLE`.
2. Read stdout as authoritative **Plan Scope Constraints** (domain + role).

</HARD-GATE>

## Commands

### `start` — Session-level, run before each design document

> Prerequisite: diagnostic `decision-doc` Delivered for this cycle.

**Phase 1:** Identify active cycle — `_runtime.md` § Session Foundation. Do not run start.py until `$CYCLE_ID` is confirmed.

**Phase 2:** Run start

```bash
python3 "$SKILL_ROOT/compose-kernel/scripts/core/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --profile tech-design \
  --run-mode tech
```

- Requires `tech-diagnostic` in `{cycle_id}/delivered-refs.json` (written when tech-diagnostic **delivers**). `start.py` snapshots it into `workflow-state.delivered_refs`; Initializing reads the snapshot.

To resume an in-progress design document, do not run start again — run `$SESSION_INFO --view session`.

---

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.

**Drafting — code reference** — Read codebase narrowly when decision-doc or section intent points at concrete paths; do not scan the whole repo.

---

## Drafting Rules

**Entry:** Step 1 → Step 2 → Step 3, or resume via `$SESSION_INFO --view session`.
**Drafting states:** `Ready → RoundIteration → FreeEdit`.

**After Initializing completes:** present summary; user may enter **Step 2 — RoundIteration**, **Evaluating**, or **Deliver** (skip Round/FreeEdit).

#### Step 1 — Initializing

Compose design-doc from decision-doc (`I*` / `F` / `C` per section; see initializing-runner Theory). No mapping paste.

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

3. **Pause gate:** Present runner return summary and `design-doc.md` path. Ask: Round refine, Evaluate, or Deliver?

#### Step 2 — RoundIteration

Same section-gated loop as tech-plan (see `tech-plan/SKILL.md` Step 2). Use `$ROUND_CONTROL` with `--profile tech-design`.

**Entry:** `$DRAFT_CONTROL begin-round` → parse JSON `round` as **N**.

Per round N: **2a** probe (`round-probe-input` → prober-runner) → **2b** gap display → **2c** refiner → **2d** convergence check. On converge → `$DRAFT_CONTROL advance-to-freeedit` or `advance-round`.

Prober/refiner: pass `--profile tech-design` on `$FETCH_COMPOSE section-registry` / `section-kw-criteria`.

#### Step 3 — FreeEdit

User-driven edits on `design-doc.md`. When done → Evaluate or Deliver.

### Evaluating Rules

Read `{$SKILL_ROOT}/eval/eval-rules.md` and follow its instructions (only when user explicitly chooses Evaluate).

When eval-rules completes, follow its exit branch:

- **Deliver** → **ReadyForDelivery Rules** below.

**Dimensions (feature):**

| Dim | Id | Focus |
|-----|-----|-------|
| d1 | `codebase-consistency` | Explicit code/module/interface citations in ST/IF/CTX vs repo |
| d2 | `solution-quality` | P1–P4 + design supplements (D1–D3) on design-doc |

### ReadyForDelivery Rules

1. Run `$SESSION_CONTROL ready-for-delivery`. On failure → Blocking.

2. Run `$SESSION_INFO --view delivery-preview`. On failure → Blocking. On success: show a delivery preview; full design-doc only if asked.

3. Wait for explicit delivery confirmation.

4. Run `$SESSION_CONTROL deliver`. On failure → Blocking. On success → **Delivery Rules** below.

### Delivery Rules

1. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. On success: prompt next stages when present.

---

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose-kernel/references/gap-display.md` | Round Iteration **2b** |
| `{SKILL_ROOT}/compose-kernel/runners/prober-runner/SKILL.md` | Round **2a** |
| `{SKILL_ROOT}/compose-kernel/runners/refiner-runner/SKILL.md` | Round **2c** |
| `{$SKILL_ROOT}/eval/eval-rules.md` | Evaluating (user-initiated) |

Template SSOT: [tech-design templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/tech-design)

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-design --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-design <subcommand>` |
| `{SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md` | Step 1 — initializing-runner |
| `$DRAFT_CONTROL` | `python3 "$SKILL_DIR/scripts/drafting/draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$ROUND_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/section_round_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" --profile tech-design --round {N} <subcommand>` |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-design` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile tech-design --project-root "$(pwd)"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/eval/scripts/eval_control.py" --workflow tech-design --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |

Subcommands and stdout: script module docstrings or `--help`.
