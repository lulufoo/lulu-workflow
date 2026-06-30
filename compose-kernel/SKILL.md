---
name: compose
description: >-
  Profile-driven compose engine (I*/F/C), session control, start orchestration,
  drafting control, evaluation handoff, and delivery support for structured
  document stages (tech-design, tech-plan, product-spec). Consumed by stage
  holder skills.
---

# compose

Shared compose engine consumed by stage holder skills (`tech-design`, `tech-plan`, `product-spec`). Stage holders provide profile identity and user-facing workflow rules; this engine owns the reusable scripts and schemas.

`DEFAULT_COMPOSE_PROFILE_ID` (`tech-plan`) is for kernel tests and `load_profile()` fallbacks only. Production invocations must pass `--profile` via stage macros or entry scripts.

## Compose profiles

Authoring SSOT: `{WORKFLOW_ROOT}/{stage}/compose-profile.json` (tech-plan, tech-design, product-spec). At session start, stage `start` writes `.compose-profile-path` under `{cache_subdir}/` pointing at that file. Runtime `load_profile()` resolves via the pointer when `project_root` and `cycle_id` are set; delivery/schema tools read the authoring file directly.

## Script Macros

Macro expansion: `{$SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion.

Fetch compose framework templates on demand; **do not** read `workflow-config.json` directly. Scheme roles: `schemes/compose-template-scheme.json` (mapped per profile in `compose-profile.json` → `framework_templates`).

| Macro | Command |
|-------|---------|
| `$START_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/core/start.py" --profile <profile_id> --profile-path "$SKILL_ROOT/<stage>/compose-profile.json"` |
| `$DRAFT_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/draft_control.py" --profile <profile_id> --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile <profile_id> --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/compose_doc_control.py" <subcommand> [args...]` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/init_compose_validation.py" validate --revision-dir <dir> --compose-doc <path> --profile <profile_id> --project-root "$(pwd)"` |

Subcommands and stdout: script module docstrings or `--help`.
