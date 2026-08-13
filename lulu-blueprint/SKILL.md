---
name: lulu-blueprint
description: >-
  Topic-cycle product architecture shaping stage. Use when cycle_type is topic and
  lulu-bet is Delivered.
disable-model-invocation: true
---

# lulu-blueprint

Domain holder for the product-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Delivered `decision-package` from `lulu-bet`. Produces **product-doc.md**.

**Scope:** Topic cycles only. Feature PRD cycles use `lulu-spec`.

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR`; set `$SKILL_DIR` = `$SKILL_ROOT/lulu-blueprint`; then Session Foundation.
</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
Continue from its `## Start`.
</HARD-GATE>

## Compose Inputs

1. Run `$BLUEPRINT_PREFLIGHT`. Bind stdout `profile_path` as `$PROFILE_PATH` and `scope_package` as `$SCOPE_PACKAGE`.

Run mode is always `product`. To resume, run `$SESSION_INFO --view session` instead of Start.

## Script Macros

| Macro | Command |
|---|---|
| `$BLUEPRINT_PREFLIGHT` | `python3 "$SKILL_DIR/scripts/start/product_blueprint_preflight.py" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |

## Reference documents

Template SSOT: [blueprint templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/blueprint)
