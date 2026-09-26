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

Macro expansion: `{SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion. Non-zero exit → Blocking: stop, report (stderr / exit code), wait for user direction.

| Macro | Command |
|-------|---------|
| `$START_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/session/start.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID" --profile-path "$PROFILE_PATH" --scope-package "$SCOPE_PACKAGE"` |
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose/scripts/session/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/session/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$L_SHELL` | `python3 "$SKILL_ROOT/compose/scripts/session/l_shell_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$AGENDA_CTL` | `python3 "$SKILL_ROOT/agenda/scripts/agenda_control.py" <subcommand> --project-root "$(pwd)" --cycle-id "$CYCLE_ID" [args...]` |

Subcommands and stdout: script module docstrings or `--help`.

L-execution macros are defined in `{SKILL_ROOT}/compose/references/l-execution.md`. Load that file before using them.

## Lifecycle

```mermaid
stateDiagram-v2
  [*] --> Split: Start
  Split --> Working: leave-split
  Working --> ReadyForDelivery: all L Completed and unfrozen
  ReadyForDelivery --> Working: Modify
  ReadyForDelivery --> Delivered: Deliver
```

Route only from `$SESSION_INFO` / `$L_SHELL` stdout. Do not compute the next L by hand.

## Entry

### Start

Run `$START_COMPOSE`. On failure → Blocking.
Load `{SKILL_ROOT}/compose/references/compose-ontology.md` once.

**Done:** `$CURRENT_STATE=Split`.

### Bind context

Run `$SESSION_INFO --view session`, then bind:

| Cite | JSON field | Use |
|------|------------|-----|
| `$REVISION_DIR` | `revision_dir` | revision-scoped tools |
| `$DEMAND_MANIFEST` | `demand_manifest` | Delivery demand atomization; skip when null |
| `$CURRENT_STATE` | `workflow_state.current_state` | Outer routing |
| `$L_VIEW` | `l_view` | order, focus, next_actions |

## Split

**Session state:** `Split`. The L chain is already published.

1. Run `$SESSION_CONTROL leave-split`. On failure → Blocking.
2. From stdout `node_ids` and `focus`: tell the user it is an ordered chain of N L; focus = `focus`.
3. Continue with ## Working.

**Done:** `$CURRENT_STATE=Working`.

## Working

**Session state:** `Working`.

Load `{SKILL_ROOT}/compose/references/l-chain.md` and follow it: status loop, focus, advance, align, backtrack, view. Running the focus L is `references/l-execution.md`, loaded from l-chain.

**Done:** every L `Completed` and unfrozen → ## ReadyForDelivery.

## ReadyForDelivery

Ask: Deliver or Modify.

- Deliver → ## Delivery.
- Modify → `$SESSION_CONTROL return-to-working --confirm`. Then ## Working. Preview is not required.

## Delivery

1. Run `$SESSION_INFO --view delivery-preview`. On failure → Blocking. Show the preview; full compose document only if asked.
2. Wait for explicit delivery confirmation.
3. **Demand manifest (only when `$DEMAND_MANIFEST` is present):** enumerate delivered demands per `$DEMAND_MANIFEST.unit_rule`, then `$SESSION_CONTROL write-demand-manifest --units-json '<JSON array>'`. Skip when `$DEMAND_MANIFEST` is null. On failure → Blocking.
4. Run `$SESSION_CONTROL deliver --confirm`. On failure → Blocking (including open stage-agenda blockers — resolve via `$AGENDA_CTL` then retry).
5. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. Prompt next stages when present.

Stage-agenda items live under the revision dir; orchestration: `{SKILL_ROOT}/agenda/SKILL.md`.

## Reference

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/references/compose-ontology.md` | Start, once per session |
| `{SKILL_ROOT}/compose/references/l-chain.md` | Working |
| `{SKILL_ROOT}/compose/references/l-execution.md` | Execute, Reopen, Backtrack (from l-chain) |
| `{SKILL_ROOT}/eval/SKILL.md` | Loaded from l-execution Evaluating |
| `{SKILL_ROOT}/agenda/SKILL.md` | Delivery blockers |
