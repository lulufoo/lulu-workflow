---
name: lulu-design
description: >-
  Produce and deliver a design-doc for a feature cycle.
disable-model-invocation: true
---

# lulu-design

Own the stage-specific contract and inputs for composing the design doc.
Completion is delivery through the shared `compose` engine.

## Contract

| Boundary | Contract |
|---|---|
| Scope | Feature cycle only |
| Prerequisite | Delivered `lulu-approach` as a `decision-package`. Product mode also requires Delivered `lulu-spec`. |
| Output | Delivered design doc |
| Ownership | `lulu-design` prepares stage inputs; `compose` owns orchestration |

## Runtime

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and:

- loaded `$SKILL_ROOT` and `$PLATFORM` from `## Platform Context`
- established `$CYCLE_ID` and `$CYCLE_TYPE` via `## Session Foundation`
- set `$SKILL_DIR` = `$SKILL_ROOT/lulu-design`

</HARD-GATE>

## Compose

1. Run `$DESIGN_PREFLIGHT`. Bind stdout `profile_path` as `$PROFILE_PATH` and `scope_package` as `$SCOPE_PACKAGE`.

<HARD-GATE>
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
Continue from its `## Entry`.
</HARD-GATE>

## Script Macros

| Macro | Command |
|---|---|
| `$DESIGN_PREFLIGHT` | `python3 "$SKILL_DIR/scripts/start/tech_design_preflight.py" --cycle-id "$CYCLE_ID"` |
