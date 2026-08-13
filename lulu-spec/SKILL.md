---
name: lulu-spec
description: >-
  Use when: 产品规格, feature PRD, product spec, product-doc,
  lulu-dev-workflow lulu-spec, product delivered, 产品文档.
disable-model-invocation: true
---

# lulu-spec

Domain holder for the product-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Delivered `decision-package` from `lulu-bet`, projected to this revision's `scope-package`. Produces **product-doc.md** — feature product specification for human sign-off before `lulu-approach`.

**Scope:** Feature cycle only. Topic/shaping cycles are out of scope (future `lulu-blueprint`).

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- `$SKILL_DIR` = `$SKILL_ROOT/lulu-spec` (before Session Foundation)
- Feature identification logic from `## Session Foundation`

</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
Continue from its `## Start`.
</HARD-GATE>

## Compose Inputs

1. Run `$SPEC_PREFLIGHT`. Bind stdout `profile_path` as `$PROFILE_PATH` and `scope_package` as `$SCOPE_PACKAGE`.

Requires `lulu-bet` in delivered-refs. Run mode is always `product`. To resume, run `$SESSION_INFO --view session` instead of Start.

## Script Macros

| Macro | Command |
|---|---|
| `$SPEC_PREFLIGHT` | `python3 "$SKILL_DIR/scripts/start/product_spec_preflight.py" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |

## Reference documents

Template SSOT: [spec templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/spec)
