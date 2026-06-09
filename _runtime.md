## Platform Context

**Detect once at session start, substitute `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, and `$CACHE_DIR` throughout:**

| | Cursor | Copilot |
|---|---|---|
| `$PLATFORM` | `cursor` | `copilot` |
| `$SKILL_ROOT` | `~/.cursor/skills/lulu-dev-workflow` | `~/.copilot/skills/lulu-dev-workflow` |
| `$WORKFLOW_DIR` | `.cursor/lulu-dev-workflow` | `.github/lulu-dev-workflow` |
| `$CACHE_DIR` | `.cache/cursor/lulu-dev-workflow` | `.cache/copilot/lulu-dev-workflow` |

> **Detect:** `COPILOT_AGENT=1` env var → Copilot; `VSCODE_TARGET_SESSION_LOG` template variable present → Copilot; otherwise → Cursor.

## Session Foundation

### Active Context

`active-context.json` is indexed by Cursor/Copilot `conversation_id`:

```json
{ "<conversation_id>": { "cycle_id": "...", "stage": "tech-plan", "cycle_type": "feature" } }
```

- `cycle_type`: `"topic"` | `"feature"` — backward compat: absent field is treated as `"feature"`
- Re-starting a different feature in the **same** conversation overwrites that conv entry (one active workflow per conversation)

**Output variables:** `$CYCLE_ID` · `$EXECUTION_MODE` (`"guided"` | `"autonomous"`)

### Execution Mode

| Mode | Value | AI Behavior |
|------|-------|-------------|
| Guided | `"guided"` | Proactively leads, asks, recommends; waits at key gates |
| Autonomous | `"autonomous"` | Executes instructions only; no unprompted advances; tech-line auto-chains feature cycles |

`$EXECUTION_MODE` is set during Feature Resolution and applies to all subsequent stages.

#### Initial Mode Resolution

1. `cycle_id` not in `cycles.json` → `"guided"`
2. Value is an object → use `object.execution_mode`

#### Runtime Switch

The user may switch mode at any point by entering:

```
SET_EXECUTION_MODE: <mode>
```

On detection: `$EXECUTION_MODE ← <mode>`, effective immediately for all remaining stages.
Announce: `Execution mode → <mode>`

Sub-SKILLs do not emit this command directly. They may prompt the user that switching is available.

### Template Fetch

Workflow templates (spec, meta, evaluation frameworks) load via the shared CLI — not hand-written `gh api` in SKILL docs.

```bash
python3 "$SKILL_ROOT/scripts/fetch_template.py" \
  --section <section> --key <key> \
  --project-root "<project_root>"
```

- **Cache:** `$CACHE_DIR/.template/{section}/{key}.md`
- **Refresh:** delete the cache file or pass `--force`
- **Prerequisite:** `gh` CLI authenticated (required only on cache miss)

#### Runtime alias

The user may request a template fetch at any point:

```
FETCH_TEMPLATE: <section> <key>
```

On detection: run the CLI above with parsed args; output template content or report failure.
Announce: `Template fetched: <section>.<key>` (or report error).

Sub-SKILLs invoke the CLI directly in their execution steps; they do not emit `FETCH_TEMPLATE`.

### Feature Resolution

#### Fast Path

1. Scan conversation for latest `LULU-DEV-WORKFLOW: <id>` (skip summary blocks)
2. If found, no ambiguity signal → Initial Mode Resolution → DONE
   Ambiguity: no footer · user mentions different feature · says "switch" / "new" / "choose"

If Fast Path fails → read `../_slowpath.md` and execute Slow Path.

#### Done

- `$CYCLE_ID` confirmed
- Read workflow docs only from `$CACHE_DIR/$CYCLE_ID/`

### Feature Tracking Convention

Every workflow AI response must end with:

```
LULU-DEV-WORKFLOW: <cycle_id>
```
