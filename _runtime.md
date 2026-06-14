## Script Macros

Non-zero exit → stop and report stderr (unless noted below).

| Macro | Command |
|-------|---------|
| `$RUNTIME_CONTROL` | `python3 "$SKILL_ROOT/scripts/runtime_control.py" --project-root "$(pwd)" <subcommand> [args...]` |
| `$RESOLVE_PLATFORM_CONTEXT` | `$RUNTIME_CONTROL resolve-platform-context` |
| `$RESOLVE_SESSION_CONTEXT` | `$RUNTIME_CONTROL resolve-session-context` |
| `$SET_EXECUTION_MODE` | `$RUNTIME_CONTROL set-execution-mode --cycle-id "$CYCLE_ID" --mode <mode>` |
| `$FETCH_TEMPLATE` | `python3 "$SKILL_ROOT/scripts/fetch_template.py" --section <section> --key <key> --project-root "$(pwd)" --platform $PLATFORM` |

Subcommands and stdout: `runtime_control.py` / `fetch_template.py` module docstring or `--help`.

## Platform Context

When `$PLATFORM`, `$SKILL_ROOT`, `$WORKFLOW_DIR`, or `$CACHE_DIR` is needed: `$RESOLVE_PLATFORM_CONTEXT`.

Non-zero exit → stop. Map stdout JSON: `platform`→`$PLATFORM`, `skill_root`→`$SKILL_ROOT`, `workflow_dir`→`$WORKFLOW_DIR`, `cache_dir`→`$CACHE_DIR`.

## Session Context

When `$CYCLE_ID`, `$STAGE`, `$CYCLE_TYPE`, or `$EXECUTION_MODE` is needed: `$RESOLVE_SESSION_CONTEXT`.

Exit 0 always; empty fields → Feature Resolution below. Map stdout: `cycle_id`→`$CYCLE_ID`, `cycle_type`→`$CYCLE_TYPE`, `stage`→`$STAGE`, `execution_mode`→`$EXECUTION_MODE`.

| Mode | Behavior |
|------|----------|
| `guided` | Lead, ask, recommend; wait at gates |
| `autonomous` | Execute only; tech-line auto-chains feature cycles |

User sends `SET_EXECUTION_MODE: <mode>` → `$SET_EXECUTION_MODE --mode <mode>`; non-zero exit → stop; announce `Execution mode → <mode>`.

## Template Fetch

Direct `fetch_template.py` usage is forbidden. Use `$FETCH_TEMPLATE <section> <key>` or `$FETCH_TECH_PLAN <role>` (`tech-plan/SKILL.md` → Script Macros).

- Success → output body; announce `Template fetched: <section>.<key>`
- Failure → stop current step
- Cache: `$CACHE_DIR/.template/{section}/{key}.md`

## Feature Resolution

1. Scan conversation for latest `LULU-DEV-WORKFLOW: <id>` (skip summary blocks)
2. Found and no ambiguity → set `$CYCLE_ID`; read workflow docs from `$CACHE_DIR/$CYCLE_ID/` only
3. Ambiguity (no footer · different feature · "switch"/"new"/"choose") or miss → read `../_slowpath.md`

## Feature Tracking Convention

Every workflow AI response must end with:

```
LULU-DEV-WORKFLOW: <cycle_id>
```
