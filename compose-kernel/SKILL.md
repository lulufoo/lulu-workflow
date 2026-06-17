---
name: compose-kernel
description: >-
  Shared compose engine (I*/F/C), session, and section-round tooling for
  structured technical document stages (tech-plan, future tech-design /
  tech-arch). Not user-invoked; consumed by stage shells.
---

# compose-kernel

Internal library for structured technical document authoring. Users invoke stage shells (`tech-plan`, etc.), not this skill.

## Boundary

**Kernel** = `compose-kernel/` below. **Shell** = stage directory (e.g. `tech-plan/`). Shell SKILL macros call into kernel; kernel does not include shell-only Drafting orchestration.

### In kernel (`compose-kernel/`)

| Path | Contents |
|------|----------|
| `scripts/core/` | Session entrypoints (`start`, `session_control`, `session_info`, `archive`, `workflow_common`) |
| `scripts/schema/session/` | Session/cycle schemas (`workflow_state`, `session_state`, `human_delivery_gate`, `profile`, `transition_registry`) |
| `transitions/` | Shared compose session transition table (`compose-session.json`) |
| `schemes/` | Compose template scheme (`compose-template-scheme.json`) |
| `scripts/schema/section/registry/` | Section registry core (`section_registry`, `section_dependency`, `outline_registry`) |
| `scripts/schema/section/round/` | Round runtime artifacts (`section_pointer`, `probe_report`, `refiner_artifact`) |
| `scripts/schema/section/document/` | Tech-doc presentation I/O (`tech_doc_schema`) |
| `scripts/schema/section/scope/` | Compose-scope instance schemas (role, domain, `schema_common`) |
| `scripts/section/` | `section_round_control` (section-gated Round Iteration) |
| `scripts/scope/` | `scope_resolver` (role/domain constraint resolver CLI) |
| `scripts/io/` | `fetch_compose_framework` (compose template fetch by scheme role) |
| `templates/` | Ledger seed templates (`anchor-ledger`, `skip-ledger`) |
| `runners/` | initializing, prober, refiner runner SKILLs |
| `references/` | `compose-theory.md`, `gap-display.md` |
| `profiles/` | Stage profile JSON (`tech-plan`, placeholders) |

### In shell only (`tech-plan/` — not in kernel)

| Path | Contents |
|------|----------|
| `scripts/drafting/draft_control.py` | Inner Drafting state machine (Initializing / Round / FreeEdit) |
| `scripts/drafting/drafting_progress_schema.py` | `drafting-progress.md` schema |
| `scripts/eval/` | Eval adapter + corpus policy (`tech_plan_eval_adapter`, `tech_plan_eval_policy`) |
| `scripts/hook_guard.py` | Active-session Write/Edit cache boundary (`HOOK_COMMAND` target) |
| `scripts/tests/` | Shell script pytest suite |
| `SKILL.md` | Full Drafting / Evaluating orchestration text |
| `dimension-defs/` | Feature Evaluating dimension definitions |

`draft_control.py` is **not** under `compose-kernel/scripts/`.

## Profiles

Stage behavior is driven by `profiles/{profile_id}.json`. Default active profile: `tech-plan`.

Validate profiles:

```bash
python3 "$SKILL_ROOT/compose-kernel/scripts/schema/session/profile_schema.py" --validate
```

## Paths

`scripts/core/workflow_paths.py` is the SSOT for `WORKFLOW_ROOT`, `CORE_SCRIPTS`, `SECTION_SCRIPTS`, `SCOPE_SCRIPTS`, `IO_SCRIPTS`, `SCHEMA_SECTION_*_SCRIPTS`, `SCHEMA_SESSION_SCRIPTS`, `KERNEL_TEMPLATES`, and `load_profile()`.
