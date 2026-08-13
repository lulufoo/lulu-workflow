---
name: compose
description: >-
  Internal compose engine; load only via stage holder HARD-GATE — do not invoke directly.
---

# compose

Shared compose engine for stage holders. It manages an ordered chain of L slices through delivery. Single-L execution lives in `references/l-execution.md`.

## Inputs

| Variable | Required | Source | Use |
|---|---|---|---|
| `$CYCLE_ID` | yes | Holder runtime foundation | Active cycle |
| `$PROFILE_PATH` | yes | Holder preflight | Runtime `compose-profile.json` |
| `$SCOPE_PACKAGE` | yes | Holder preflight | Normalized `scope-package.json` |

## Script Macros

Macro expansion: `{$SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion. Non-zero exit → Blocking: stop, report (stderr / exit code), wait for user direction.

Fetch compose framework templates on demand. Scheme roles: `schemes/compose-template-scheme.json` (mapped per profile in `compose-profile.json` → `framework_templates`).

### Outer

| Macro | Command |
|-------|---------|
| `$START_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/core/start.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID" --profile-path "$PROFILE_PATH" --scope-package "$SCOPE_PACKAGE"` |
| `$HOLDER_FINALIZE` | `python3 "$SKILL_ROOT/compose/scripts/core/holder_finalize.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID" --profile-id <profile_id> --start-id <start_id> --active-doc <n> --profile-digest <sha256> --confirm` |
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$L_SHELL` | `python3 "$SKILL_ROOT/compose/scripts/core/l_shell_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$AGENDA_CTL` | `python3 "$SKILL_ROOT/agenda/scripts/agenda_control.py" <subcommand> --project-root "$(pwd)" --cycle-id "$CYCLE_ID" [args...]` |

### L-execution

| Macro | Command |
|-------|---------|
| `$L_STEP` | `python3 "$SKILL_ROOT/compose/scripts/section/l_step_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$INDUCTIVE_FACTS_PROJ` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_facts_projection.py"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$EVAL_HANDOFF` | `python3 "$SKILL_ROOT/compose/scripts/core/eval_handoff_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/core/compose_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" -- <subcommand>` |
| `$FACT_INTAKE_EVAL_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-intake-eval/scripts/fact_intake_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" -- <subcommand>` |
| `$ATOMIZE_EVAL_CONTROL` | Same command as `$FACT_INTAKE_EVAL_CTL` (retired name; prefer `$FACT_INTAKE_EVAL_CTL`) |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py" <subcommand> [args...]` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_write_state_control.py"` |
| `$WRITING_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/writing_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc <path> --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

Subcommands and stdout: script module docstrings or `--help`.

## Outer spine

```text
Start / Bind
  → leave Split
  → Working loop:
       $L_SHELL status
       execute-current → load references/l-execution.md
       advance         → $L_SHELL advance
       align-next      → review successor → $L_SHELL unfreeze
       reopen-current  → load references/l-execution.md
       backtrack       → $L_SHELL backtrack --confirm → l-execution.md
       view            → $L_SHELL view
       ready-for-delivery → $SESSION_CONTROL ready-for-delivery
  → ReadyForDelivery:
       Deliver → preview → confirm → demand manifest (if required) → deliver --confirm
       Modify  → return-to-working --confirm
```

Route only from `$SESSION_INFO` / `$L_SHELL` stdout. Do not compute the next L by hand.

## Start

1. Confirm Inputs.
2. Run `$START_COMPOSE`. On failure → Blocking.
3. Bind `start_id`, `active_doc`, `profile_id`, `profile_digest` from stdout.
4. Run `$HOLDER_FINALIZE` with those fields and `--confirm`. On failure → Blocking.

## Bind context

Run `$SESSION_INFO --view session`, then bind:

| Cite | JSON field | Use |
|------|------------|-----|
| `$REVISION_DIR` | `revision_dir` | revision-scoped tools |
| `$DEMAND_MANIFEST` | `demand_manifest` | Delivery demand atomization; skip when null |
| workflow state | `workflow_state.current_state` | Outer routing |
| L-shell | `l_shell` | order, focus, next_actions |

## Split

**Session state:** Start lands in **`Split`**. The L chain is already published.

1. Run `$SESSION_CONTROL leave-split`. On failure → Blocking.
2. From stdout `node_ids` and `focus`: tell the user the work is an ordered chain of N L units; current focus = `focus`.
3. Continue with ## Working.

**Done:** `current_state=Working`.

## Working

**Session state:** `Working`.

Loop: run `$L_SHELL status` and follow `next_actions`. On inner failure → Blocking; do not advance focus.

### Execute current

Load `{SKILL_ROOT}/compose/references/l-execution.md` and follow it for the current focus. When that L is `Completed`, return here.

### Advance

Run `$L_SHELL advance`. No confirm. On `alignment_required` → **Align next**. On `next_action=ready-for-delivery` → ask overall delivery intent, then `$SESSION_CONTROL ready-for-delivery`.

### Align next

Read-only: review whether the frozen successor still holds given the completed prefix. If yes, run `$L_SHELL unfreeze --expected-fingerprint <stdout fingerprint> --confirm`.

### Reopen current

Load `references/l-execution.md` and follow **Reopen**.

### Backtrack

Run `$L_SHELL backtrack --target Lx --confirm`. Then load `references/l-execution.md` and continue from **FreeEdit**.

### View

Run `$L_SHELL view --target Lx`. Allowed in any session macrostate. Zero writes.

## ReadyForDelivery

Ask overall delivery intent.

- Deliver → ## Delivery.
- Modify → `$SESSION_CONTROL return-to-working --confirm`. Then ## Working. Preview is not required.

## Delivery

1. Run `$SESSION_INFO --view delivery-preview`. On failure → Blocking. Show the preview; full compose document only if asked.
2. Wait for explicit delivery confirmation.
3. **Demand manifest (only when `$DEMAND_MANIFEST` is present):** enumerate delivered demands per `$DEMAND_MANIFEST.unit_rule`, then `$SESSION_CONTROL write-demand-manifest --units-json '<JSON array>'`. Skip when `$DEMAND_MANIFEST` is null. On failure → Blocking.
4. Run `$SESSION_CONTROL deliver --confirm`. On failure → Blocking (including open stage-agenda blockers — resolve via `$AGENDA_CTL` then retry).
5. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. Prompt next stages when present.

Stage-agenda items live under the revision dir; orchestration: `$SKILL_ROOT/agenda/SKILL.md`.

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/references/l-execution.md` | Working → execute-current / reopen-current / after backtrack |
| `{$SKILL_ROOT}/eval/SKILL.md` | Loaded from l-execution Evaluating |
| `{SKILL_ROOT}/agenda/SKILL.md` | Delivery blockers |
