---
name: lulu-blueprint
description: >-
  Produce and deliver a product-doc for a topic cycle.
disable-model-invocation: true
---

# lulu-blueprint

Own the stage-specific contract and inputs for composing the product doc.
Completion is delivery through the shared `compose` engine.

## Contract

| Boundary | Contract |
|---|---|
| Scope | Topic cycle only |
| Prerequisite | Delivered `lulu-bet` as a `decision-package` |
| Output | Delivered product doc |
| Ownership | `lulu-blueprint` prepares stage inputs; `compose` owns orchestration |

## Runtime

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and:

- loaded `$PROJECT_ROOT`, `$SKILL_ROOT`, and `$PLATFORM` from `## Platform Context`
- established `$CYCLE_ID` and `$CYCLE_TYPE` via `## Session Foundation`
- set `$SKILL_DIR` = `$SKILL_ROOT/lulu-blueprint`

</HARD-GATE>

## Compose

1. Run `$BLUEPRINT_PREFLIGHT`. Bind stdout `profile_path` as `$PROFILE_PATH` and `scope_package` as `$SCOPE_PACKAGE`.

<HARD-GATE>
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
Continue from its `## Entry`.
</HARD-GATE>

## Script Macros

| Macro | Command |
|---|---|
| `$BLUEPRINT_PREFLIGHT` | `python3 "$SKILL_DIR/scripts/start/product_blueprint_preflight.py" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |
