---
name: compose-kernel
description: >-
  Shared compose engine (I*/F/C), session, and section-round tooling for
  structured technical document stages (tech-plan, future tech-arch).
  Not user-invoked; consumed by stage shells.
---

# compose-kernel

Internal library — consumed by stage shells (`tech-plan`, etc.); not user-invoked.

## Script Macros

Macro expansion: `{$SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion.

Fetch compose framework templates on demand; **do not** read `workflow-config.json` directly. Scheme roles: `schemes/compose-template-scheme.json` (mapped per profile in `profiles/{profile_id}.json` → `framework_templates`).

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --project-root "$(pwd)"` |
| `$ROUND_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/section_round_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" --round {N} <subcommand> [args...]` |

Subcommands and stdout: script module docstrings or `--help`.
