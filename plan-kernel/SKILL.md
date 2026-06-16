---
name: plan-kernel
description: >-
  Shared session and section-round tooling for planning stages (tech-plan,
  future tech-design / tech-arch). Not user-invoked; consumed by stage shells.
---

# plan-kernel

Internal library for planning workflows. Users invoke stage shells (`tech-plan`, etc.), not this skill.

## Boundary

**Kernel** = `plan-kernel/` below. **Shell** = stage directory (e.g. `tech-plan/`). Shell SKILL macros call into kernel; kernel does not include shell-only Drafting orchestration.

### In kernel (`plan-kernel/`)

| Path | Contents |
|------|----------|
| `scripts/core/` | Session, `start`, archive, `workflow_state`, `session_control`, `session_info` |
| `scripts/section/` | `round_control`, section schemas, `eval_workflow_adapter`, `plan_scope` |
| `runners/` | initializing, prober, refiner runner SKILLs |
| `references/` | `compose-theory.md`, `gap-display.md` |
| `profiles/` | Stage profile JSON (`tech-plan`, placeholders) |

### In shell only (`tech-plan/` — not in kernel)

| Path | Contents |
|------|----------|
| `scripts/draft_control.py` | Inner Drafting state machine (Initializing / Round / FreeEdit) |
| `scripts/drafting_progress_schema.py` | `drafting-progress.md` schema |
| `scripts/hook_guard.py` | Active-session Write/Edit cache boundary (`HOOK_COMMAND` target) |
| `SKILL.md` | Full Drafting / Evaluating orchestration text |
| `corpora/`, `constraints/`, `templates/` | Eval stamps, role/domain instances, ledger templates |
| `transition-whitelist.json` | Outer session transition whitelist |

`draft_control.py` is **not** under `plan-kernel/scripts/`.

## Profiles

Stage behavior is driven by `profiles/{profile_id}.json`. Default active profile: `tech-plan`.

Validate profiles:

```bash
python3 "$SKILL_ROOT/plan-kernel/scripts/core/profile_schema.py" --validate
```

## Paths

`scripts/core/workflow_paths.py` is the SSOT for `WORKFLOW_ROOT`, `CORE_SCRIPTS`, `SECTION_SCRIPTS`, and `load_profile()`.
