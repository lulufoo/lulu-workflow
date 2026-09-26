---
name: lulu-plan
description: >-
  Produce and deliver an implementation-ready tech-doc for a feature cycle.
disable-model-invocation: true
---

# lulu-plan

Own the stage-specific contract and inputs for composing the plan doc.
Completion is delivery through the shared `compose` engine.

## Contract

| Boundary | Contract |
|---|---|
| Scope | Feature cycle only |
| Prerequisite | Product mode: Delivered `lulu-spec` and `lulu-design`. Tech mode: Delivered `lulu-design`, or `lulu-approach` as a `decision-package`. |
| Output | Delivered plan doc |
| Ownership | `lulu-plan` prepares stage inputs; `compose` owns orchestration |

## Runtime

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and:

- loaded `$PROJECT_ROOT`, `$SKILL_ROOT`, and `$PLATFORM` from `## Platform Context`
- established `$CYCLE_ID` and `$CYCLE_TYPE` via `## Session Foundation`
- set `$SKILL_DIR` = `$SKILL_ROOT/lulu-plan`

</HARD-GATE>

## Compose

1. Run `$PLAN_PREFLIGHT`. Bind stdout `profile_path` as `$PROFILE_PATH` and `scope_package` as `$SCOPE_PACKAGE`.

<HARD-GATE>
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
Continue from its `## Entry`.
</HARD-GATE>

## Script Macros

| Macro | Command |
|---|---|
| `$PLAN_PREFLIGHT` | `python3 "$SKILL_DIR/scripts/start/tech_plan_preflight.py" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |
