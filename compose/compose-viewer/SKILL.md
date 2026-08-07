---
name: compose-viewer
description: >-
  Compose design viewer mount skill. Serves collab arc + facts; hard-bans
  Formal as primary source. Optional declare-use from inductive G2/G3.
---

# compose-viewer

Use when a compose caller **declares** this skill to mount the local viewer.

**Must:** mount via `$COMPOSE_VIEWER_CTL`; primary arc = collab only.  
**Must not:** use Formal `_narrative-arc.json` as primary source.

## Script Macros

| Macro | Command |
|-------|---------|
| `$COMPOSE_VIEWER_CTL` | `python3 "$SKILL_ROOT/compose/compose-viewer/scripts/compose_viewer_control.py"` |

Subcommands: `--help` · `mount` · `status` · `stop`.

## DONE / failure

- **DONE (mount):** exit 0; stdout is **URL only** (one line).
- **DONE (status/stop):** exit 0; JSON on stdout.
- **Failure:** non-zero; Formal banned or server start error on stderr.
