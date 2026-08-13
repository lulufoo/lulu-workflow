---
name: lulu-arch
description: >-
  Topic-cycle technical architecture shaping stage. Use when cycle_type is topic and
  lulu-approach is Delivered.
disable-model-invocation: true
---

# lulu-arch

Domain holder for the arch-doc compose document. Delegates full Drafting / Evaluating / Delivery orchestration to the `compose` kernel.

> **Prerequisite:** Delivered `decision-package` from `lulu-approach`. Produces **arch-doc.md**.

**Scope:** Topic cycles only. Feature technical planning uses `lulu-plan` / `lulu-design`.

<HARD-GATE name="Runtime bootstrap">
Do NOT proceed until you have read `../_runtime.md` and loaded `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR`; set `$SKILL_DIR` = `$SKILL_ROOT/lulu-arch`; then Session Foundation.
</HARD-GATE>

<HARD-GATE name="Compose engine">
Do NOT proceed until you have read `{SKILL_ROOT}/compose/SKILL.md` in full.
Continue from its `## Entry`.
</HARD-GATE>

## Compose Inputs

1. Run `$ARCH_PREFLIGHT`. Bind stdout `profile_path` as `$PROFILE_PATH` and `scope_package` as `$SCOPE_PACKAGE`.

Run mode is always `tech`. To resume, run `$SESSION_INFO --view session` instead of Start.

## Script Macros

| Macro | Command |
|---|---|
| `$ARCH_PREFLIGHT` | `python3 "$SKILL_DIR/scripts/start/tech_arch_preflight.py" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |

## Reference documents

Template SSOT: [arch templates on GitHub](https://github.com/lulufoo/lulu-workflow-framework/tree/main/lulu-dev-workflow/template/arch) (`skill-config` → `tat_*_url`)
