---
name: tech-design
description: >-
  Use when: 技术方案设计, tech design stage, design-doc,
  lulu-dev-workflow tech-design, design delivered, 设计文档.
disable-model-invocation: true
---

# tech-design

> **Prerequisite:** Delivered `decision-doc` from `tech-diagnostic`.
> **Phase 2:** Full Drafting lifecycle (Inductive → Initializing → FreeEdit) + Evaluating + Delivery wired.

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
  --profile-path "$SKILL_DIR/compose-profile.json" \
  --run-mode product|tech
```

- **tech mode** (default): requires `tech-diagnostic` in `{cycle_id}/delivered-refs.json`. Evaluating runs d1 + d2.
- **product mode**: requires both `tech-diagnostic` **and** `product-spec` in `{cycle_id}/delivered-refs.json`. Evaluating adds d3 (`intent-alignment`) — GAP/GHOST detection against the product-spec. Use `--run-mode product` when product-spec context applies.
- `start.py` validates required entries via the profile StartAdapter, then snapshots them into `workflow-state.delivered_refs`; Initializing reads the snapshot.

To resume an in-progress design document, do not run start again — run `$SESSION_INFO --view session`.

---

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.

---

## Drafting Rules

**Entry:** Step 0 → Step 1 → Step 2, or resume via `$SESSION_INFO --view session`.
**Drafting states:** `Inductive → Initialized → FreeEdit`.

**After Initializing completes:** present summary; user may enter **Step 2 — FreeEdit**, **Evaluating**, or **Deliver** (skip FreeEdit).

#### Step 0 — Inductive (mandatory)

Anchor the decision-doc in code before composing. Always run — no opt-in prompt.

**Inductive-runner** is a human-driven 4-gate spine (Shape → Grounding → Refine → Recompose): AI recommends; the **user** closes each gate. Run it **inline in this conversation** (same as `/diagnostic` gate runners). **No `$SUBAGENT_*`** — subagents cannot interact with the user.

1. Run `$DRAFT_CONTROL begin-inductive`.
   - On failure → Blocking.
   - On success → read the runner SKILL and follow its gate spine **interactively in this conversation**, with `begin-inductive` stdout as its `## Input`:

```text
Load {actual $SKILL_ROOT}/compose-kernel/runners/inductive-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
{begin-inductive stdout}
```

2. After the gate spine completes (user confirms Gate 4 recompose), run `$DRAFT_CONTROL inductive-complete`. On failure → Blocking. It emits per-section scope files under `inductive-scope/` consumed by Step 1.

#### Step 1 — Initializing

Compose design-doc (`I*` / `F` / `C` per section; see initializing-runner Theory). No mapping paste. **`decision-doc.md` is the scope SSOT.** When inductive produced per-section scope files, `begin-init` passes their directory as `INDUCTIVE_DIR`; init reads each section's slice as code-anchored substance **alongside** decision-doc (decision-doc stays the completeness anchor — inductive slice enriches, never replaces).

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

3. **Pause gate:** Present runner return summary and `design-doc.md` path. Ask: FreeEdit, Evaluate, or Deliver?
   - **FreeEdit** → run `$DRAFT_CONTROL advance-to-freeedit`. On failure → Blocking. Proceed to **Step 2 — FreeEdit**.
   - **Evaluate** → **Evaluating Rules** below (skip FreeEdit).
   - **Deliver** → **ReadyForDelivery Rules** below (skip FreeEdit).

#### Step 2 — FreeEdit

User-driven edits on `design-doc.md`. When done → Evaluate or Deliver.

### Evaluating Rules

Read `{$SKILL_ROOT}/eval/eval-rules.md` and follow its instructions (only when user explicitly chooses Evaluate).

When eval-rules completes, follow its exit branch:

- **Deliver** → **ReadyForDelivery Rules** below.

- **Continue editing** → enter **Step 2 — FreeEdit** (Evaluating fix resume; skip Step 0 and Step 1).

**Dimensions (feature):**

| Dim | Id | Mode | Focus |
|-----|-----|------|-------|
| d1 | `codebase-consistency` | tech + product | Explicit code/module/interface citations in ST/IF/CTX vs repo |
| d2 | `solution-quality` | tech + product | P1–P4 + design supplements (D1–D3) on design-doc |
| d3 | `intent-alignment` | product only | GAP/GHOST detection — design-doc vs product-spec (SDCA framework) |

d3 is silently skipped when `product_ref` is absent (tech mode or product mode without product-spec delivered-ref).

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
| `{SKILL_ROOT}/compose-kernel/runners/inductive-runner/SKILL.md` | Step 0 — inductive-runner |
| `{SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md` | Step 1 — initializing-runner |
| `{$SKILL_ROOT}/eval/eval-rules.md` | Evaluating (user-initiated) |

Template SSOT: [tech-design templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/tech-design)

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-design --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-design <subcommand>` |
| `{SKILL_ROOT}/compose-kernel/runners/initializing-runner/SKILL.md` | Step 1 — initializing-runner |
| `$DRAFT_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-design <subcommand>` |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile tech-design` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile tech-design --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_DIR/scripts/tech-design_eval_control.py" --workflow tech-design --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |

Subcommands and stdout: script module docstrings or `--help`.
