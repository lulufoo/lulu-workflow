## Script Macros

<HARD-GATE name="Macro expansion">
Expand macros verbatim from the Script Macros table that defines them — include every flag; do not invoke control scripts by subcommand name alone.
</HARD-GATE>

Non-zero exit → stop and report stderr (unless noted below).

| Macro | Command |
|-------|---------|
| `$RUNTIME_CONTROL` | `python3 "$SKILL_ROOT/scripts/runtime_control.py" --project-root "$(pwd)" <subcommand> [args...]` |
| `$CYCLE_CONTROL` | `python3 "$SKILL_ROOT/scripts/cycle_control.py" --project-root "$(pwd)" --platform $PLATFORM <subcommand> [args...]` |
| `$FETCH_TEMPLATE` | `python3 "$SKILL_ROOT/scripts/fetch_template.py" --section <section> --key <key> --project-root "$(pwd)" --platform $PLATFORM` |

Subcommands and stdout: `runtime_control.py` / `cycle_control.py` / `fetch_template.py` module docstring or `--help`.

## Platform Context

When `$PLATFORM`, `$SKILL_ROOT`, `$WORKFLOW_DIR`, or `$CACHE_DIR` is needed: `$RUNTIME_CONTROL resolve-platform-context`.

Non-zero exit → stop. Map stdout JSON: `platform`→`$PLATFORM`, `skill_root`→`$SKILL_ROOT`, `workflow_dir`→`$WORKFLOW_DIR`, `cache_dir`→`$CACHE_DIR`.

## Session Foundation

Establish `$CYCLE_ID`, `$CYCLE_TYPE` via the steps below before stage work. Stage is defined by the active sub-SKILL, not session bootstrap. **Not set at section entry.**

**Prerequisite:** `$SKILL_DIR` set by caller to the active sub-SKILL directory (required before slowpath / bind).

**1. Detect ambiguity** — user message contains any of: `switch` · `new` · `choose` · different feature · explicit new topic/feature.

**2. Resolve cycle**

- **CASE 1 — Ambiguity detected**
  → read `../_slowpath.md`
  → do not run `$RUNTIME_CONTROL resolve-session-context`
  → on `$CYCLE_ID` confirmed → **4**

- **CASE 2 — No ambiguity**
  → run `$RUNTIME_CONTROL resolve-session-context` (exit 0 always)
  → if stdout `cycle_id` empty: read `../_slowpath.md`; on `$CYCLE_ID` confirmed → **4**; else **stop** (do not invoke stage commands)
  → else: **DONE** (step 3)

**3. Map stdout** (CASE 2, `cycle_id` present)

`cycle_id`→`$CYCLE_ID` · `cycle_type`→`$CYCLE_TYPE`

**4. Bind conversation** (after slowpath confirms `$CYCLE_ID` only)

```bash
$CYCLE_CONTROL bind-context --cycle-id "$CYCLE_ID" --skill-dir "$SKILL_DIR"
```

Non-zero → stop. Skip when CASE 2 already returned non-empty `cycle_id`.

<HARD-GATE>
Empty `cycle_id` → slowpath only. Do not infer `$CYCLE_ID` from files or cache.
</HARD-GATE>

## Feature Tracking Convention

Every workflow AI response must end with:

```
LULU-DEV-WORKFLOW: $CYCLE_ID
```
