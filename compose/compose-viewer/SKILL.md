---
name: compose-viewer
description: >-
  Compose design viewer mount skill. Serves a write_ready narrative arc +
  facts. Optional declare-use from inductive G2/G3.
---

# compose-viewer

Use when a compose caller **declares** this skill to mount the local viewer.

**Must:** mount via `$COMPOSE_VIEWER_CTL`; arc file must be unified
`narrative-arc` with `status=write_ready`.  
**Must not:** edit Viewer HTML in this skill; mount a non-write_ready arc.

## Script Macros

| Macro | Command |
|-------|---------|
| `$COMPOSE_VIEWER_CTL` | `python3 "$SKILL_ROOT/compose/compose-viewer/scripts/compose_viewer_control.py"` |

Subcommands: `--help` · `mount` · `status` · `stop`.

## DONE / failure

- **DONE (mount):** exit 0; stdout is **URL only** (one line).
- **DONE (status/stop):** exit 0; JSON on stdout.
- **Failure:** non-zero; invalid / non-`write_ready` arc, missing file, or server start error on stderr.
