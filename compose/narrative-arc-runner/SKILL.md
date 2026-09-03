---
name: narrative-arc-runner
description: >-
  Compose semantic narrative-arc builder for write-ready document spines.
---

# narrative-arc-runner

Produce the document's narrative spine: outline stations come from settled
facts' substance story and are ordered for Role-reviewable reading, so titles
and structure alone present a Domain-audience through-line—not a lens catalog
or fact list.

## Boundaries

**Must:** bind Input; load protocol then delivery; obtain context via
`$NARRATIVE_ARC_BUILD`; build from facts' substance story; pass pre-persist
self-check; `validate-candidate` then `write --digest` for each phase.  
**Must not:** use topic / old arc / lens order as the spine; use lens clusters;
persist a candidate that failed or skipped self-check; invent a second schema
or `formal|collab` target fork; change Viewer HTML.

## Input

```text
REVISION_DIR: <revision or inductive out dir>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
OUTPUT_PATH: <arc file relative to slice or absolute>
MOUNT: true|false
```

Default when `MOUNT` omitted: `false`.  
Do **not** paste fact bodies — read via `context`.

## Cognition

Context terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| `context` facts, `fact_ids` | `../references/cognition/fact.md` |
| `lens_tags`, registry lens relations | `../references/cognition/lens.md` |
| arc, group, leaf, station, `mapped` / `write_ready` | `../references/cognition/narrative-arc.md` |
| chapter, placement | `../references/cognition/chapter.md` |

Placement composes them:

```text
place(fact) = one leaf → one chapter,  chapter.lens ∈ fact.lens_tags
```

The arc gives topology and titles; `lens_tags` decide membership only.

## Load rule

1. Bind Input.  
2. Load `references/semantic-build-protocol.md`.  
3. Load `contracts/delivery.md` and complete the pipeline.  
4. **Must not** load retired dual-target / collab-only contracts.

## Script Macros

| Macro | Command |
|-------|---------|
| `$NARRATIVE_ARC_BUILD` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_build_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$COMPOSE_VIEWER_CTL` | `python3 "$SKILL_ROOT/compose/compose-viewer/scripts/compose_viewer_control.py"` |

Build: `--help` · `context` · `validate-candidate`.  
Arc: `--help` · `validate` · `write` · `show` · `list-chapters`.  
Viewer: `--help` · `mount` · `status` · `stop`.

## Summary

Return exactly the Summary shape in `contracts/delivery.md`.
