---
name: narrative-arc-runner
description: >-
  Compose semantic narrative-arc builder. Builds a unified write_ready arc
  (chapters included) to a caller output path; optional Viewer mount.
---

# narrative-arc-runner

Build one narrative arc to `write_ready` and persist it at the caller
`OUTPUT_PATH`. Optional Viewer mount when `MOUNT=true`.

**Must:** bind Input; load protocol then delivery; obtain context via
`$NARRATIVE_ARC_BUILD_CTL`; build from facts' substance story; pass pre-persist
self-check; `validate-candidate` then `write --digest` for each phase.  
**Must not:** use topic / old arc / lens order as the spine; use lens clusters;
persist a candidate that failed or skipped self-check; invent a second schema
or `formal|collab` target fork; change Viewer HTML.

## Input

```text
REVISION_DIR: <revision or inductive out dir>
PROJECT_ROOT: <abs project root>
COMPOSE_PROFILE: <profile id>
CYCLE_ID: <cycle id>
OUTPUT_PATH: <arc file relative to slice or absolute>
MOUNT: true|false
```

Default when `MOUNT` omitted: `false`.  
Do **not** paste fact bodies — read via `context`.

## Load rule

1. Bind Input.  
2. Load `references/semantic-build-protocol.md`.  
3. Load `contracts/delivery.md` and complete the pipeline.  
4. **Must not** load retired dual-target / collab-only contracts.

## Script Macros

| Macro | Command |
|-------|---------|
| `$NARRATIVE_ARC_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_build_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$COMPOSE_VIEWER_CTL` | `python3 "$SKILL_ROOT/compose/compose-viewer/scripts/compose_viewer_control.py"` |

Build: `--help` · `context` · `validate-candidate`.  
Arc: `--help` · `validate` · `write` · `show` · `list-chapters`.  
Viewer: `--help` · `mount` · `status` · `stop`.

## Summary

Return exactly the Summary shape in `contracts/delivery.md`.
