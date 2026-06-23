---
name: compose-kernel
description: >-
  Shared compose engine (I*/F/C), session, and section-round tooling for
  structured technical document stages (tech-plan, future tech-arch).
  Not user-invoked; consumed by stage shells.
---

# compose-kernel

Internal library — consumed by stage shells (`tech-plan`, `product-spec`, etc.); not user-invoked.

`DEFAULT_COMPOSE_PROFILE_ID` (`tech-plan`) is for kernel tests and `load_profile()` fallbacks only. Production invocations must pass `--profile` via stage macros or entry scripts.

## Compose profiles

Authoring SSOT: `{WORKFLOW_ROOT}/{stage}/compose-profile.json` (tech-plan, tech-design, product-spec). At session start, stage `start` writes `.compose-profile-path` under `{cache_subdir}/` pointing at that file. Runtime `load_profile()` resolves via the pointer when `project_root` and `cycle_id` are set; delivery/schema tools read the authoring file directly.

## Script Macros

Macro expansion: `{$SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion.

Fetch compose framework templates on demand; **do not** read `workflow-config.json` directly. Scheme roles: `schemes/compose-template-scheme.json` (mapped per profile in `compose-profile.json` → `framework_templates`).

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile <profile_id> --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/compose_doc_control.py" <subcommand> [args...]` |
| `$ROUND_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/section_round_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" --profile <profile_id> --round {N} <subcommand> [args...]` |

Subcommands and stdout: script module docstrings or `--help`.
