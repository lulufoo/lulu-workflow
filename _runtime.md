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

## Session Foundation

Resolve `$CYCLE_ID`, `$CYCLE_TYPE`, `$EXECUTION_MODE` before stage work. Stage is defined by the active sub-SKILL, not session bootstrap.

**1. Detect ambiguity** — user message contains any of: `switch` · `new` · `choose` · different feature · explicit new topic/feature.

**2. Resolve cycle**

- **CASE 1 — Ambiguity detected**
  → read `../_slowpath.md`
  → do not run `$RESOLVE_SESSION_CONTEXT`

- **CASE 2 — No ambiguity**
  → run `$RESOLVE_SESSION_CONTEXT` (exit 0 always)
  → if stdout `cycle_id` empty: read `../_slowpath.md`
  → else: **DONE** (step 3)

**3. Map stdout** (CASE 2, `cycle_id` present)

`cycle_id`→`$CYCLE_ID` · `cycle_type`→`$CYCLE_TYPE` · `execution_mode`→`$EXECUTION_MODE`

## Execution mode

- `guided` — lead, ask, wait at gates
- `autonomous` — execute only; tech-line auto-chains feature cycles

Change mode: user sends `SET_EXECUTION_MODE: <mode>` → `$SET_EXECUTION_MODE --mode <mode>`; non-zero exit → stop; announce `Execution mode → <mode>`.

## Feature Tracking Convention

Every workflow AI response must end with:

```
LULU-DEV-WORKFLOW: $CYCLE_ID
```
