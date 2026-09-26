---
name: lulu-arch
description: >-
  Produce and deliver an arch-doc for a topic cycle.
disable-model-invocation: true
---

# lulu-arch

Own the stage-specific contract and inputs for composing the arch doc.
Completion is delivery through the shared `compose` engine.

## Contract

| Boundary | Contract |
|---|---|
| Scope | Topic cycle only |
| Prerequisite | Delivered `lulu-approach` as a `decision-package` |
| Output | Delivered arch doc |
| Ownership | `lulu-arch` prepares stage inputs; `compose` owns orchestration |

## Runtime

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and:

- loaded `$PROJECT_ROOT`, `$SKILL_ROOT`, and `$PLATFORM` from `## Platform Context`
- established `$CYCLE_ID` and `$CYCLE_TYPE` via `## Session Foundation`
- set `$SKILL_DIR` = `$SKILL_ROOT/lulu-arch`

</HARD-GATE>

## Compose

1. Run `$ARCH_PREFLIGHT`. Bind stdout `profile_path` as `$PROFILE_PATH` and `scope_package` as `$SCOPE_PACKAGE`.

<HARD-GATE>
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
Continue from its `## Entry`.
</HARD-GATE>

## Script Macros

| Macro | Command |
|---|---|
| `$ARCH_PREFLIGHT` | `python3 "$SKILL_DIR/scripts/start/tech_arch_preflight.py" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |
