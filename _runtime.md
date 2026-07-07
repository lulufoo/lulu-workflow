## Script Macros

<HARD-GATE name="Macro expansion">
Expand macros verbatim from the Script Macros table that defines them — include every flag; do not invoke control scripts by subcommand name alone.
</HARD-GATE>

Non-zero exit → stop and report stderr (unless noted below).

| Macro | Command |
|-------|---------|
| `$RUNTIME_CONTROL` | `python3 "$SKILL_ROOT/scripts/runtime_control.py" --project-root "$(pwd)" <subcommand> [args...]` |
| `$FETCH_TEMPLATE` | `python3 "$SKILL_ROOT/scripts/fetch_template.py" --section <section> --key <key> --project-root "$(pwd)" --platform $PLATFORM` |

Subcommands and stdout: `runtime_control.py` / `fetch_template.py` module docstring or `--help`.

## Platform Context

When `$PLATFORM`, `$SKILL_ROOT`, `$WORKFLOW_DIR`, or `$CACHE_DIR` is needed: `$RUNTIME_CONTROL resolve-platform-context`.

Non-zero exit → stop. Map stdout JSON: `platform`→`$PLATFORM`, `skill_root`→`$SKILL_ROOT`, `workflow_dir`→`$WORKFLOW_DIR`, `cache_dir`→`$CACHE_DIR`.

## Session Foundation

Resolve `$CYCLE_ID`, `$CYCLE_TYPE`, `$EXECUTION_MODE` before stage work. Stage is defined by the active sub-SKILL, not session bootstrap.

**1. Detect ambiguity** — user message contains any of: `switch` · `new` · `choose` · different feature · explicit new topic/feature.

**2. Resolve cycle**

- **CASE 1 — Ambiguity detected**
  → read `../_slowpath.md`
  → do not run `$RUNTIME_CONTROL resolve-session-context`

- **CASE 2 — No ambiguity**
  → run `$RUNTIME_CONTROL resolve-session-context` (exit 0 always)
  → if stdout `cycle_id` empty: read `../_slowpath.md`
  → else: **DONE** (step 3)

**3. Map stdout** (CASE 2, `cycle_id` present)

`cycle_id`→`$CYCLE_ID` · `cycle_type`→`$CYCLE_TYPE` · `execution_mode`→`$EXECUTION_MODE`

## Execution mode (phase identifier)

`guided` and `autonomous` are **stage identifiers** persisted in `.cache/$PLATFORM/lulu-dev-workflow/cycles.json` (`execution_mode`). They are not user-switchable execution modes.

- `guided` — plan stage: ask and wait at gates.
- `autonomous` — tasks/code stage: choose defaults only at gates that do not need human decisions.

New cycles start with `execution_mode=guided` (see `../_slowpath.md`). After lulu-plan delivery on a **feature** container, the delivery hook writes `execution_mode=autonomous` before handoff:

`$RUNTIME_CONTROL set-execution-mode --cycle-id "$CYCLE_ID" --mode autonomous --internal`

Non-zero exit → **Blocking** (no deliver/handoff). Topic-container plan delivery skips this hook.

`$RUNTIME_CONTROL set-execution-mode` is **internal only** (`--internal` required). Users must not send `SET_EXECUTION_MODE` or call `set-execution-mode` directly.

Autonomous stage does not skip workflow steps; all stage, hook, prepare, and worktree constraints still apply.

## Feature Tracking Convention

Every workflow AI response must end with:

```
LULU-DEV-WORKFLOW: $CYCLE_ID
```
