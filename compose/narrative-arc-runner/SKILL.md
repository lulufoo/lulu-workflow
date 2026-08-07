---
name: narrative-arc-runner
description: >-
  Compose semantic narrative-arc builder. Init writes Formal arcs
  (_narrative-arc.json); G2 may write human-confirmed collaboration display
  arcs at caller-supplied paths.
---

# narrative-arc-runner

Use when a compose caller **declares** this skill to build a Formal or collab
narrative arc. Collab ≠ Formal file.

**Must:** obtain full build context via `$NARRATIVE_ARC_BUILD_CTL`; build from
facts' substance story; then validate and persist with the target control.  
**Must not:** use topic / old arc / lens order as the narrative spine; use
lens clusters; write Formal from collab control; auto-write collab without
human confirm.

## Script Macros

| Macro | Command |
|-------|---------|
| `$NARRATIVE_ARC_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_build_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$NARRATIVE_ARC_COLLAB_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_collab_control.py"` |

Build: `--help` · `context` · `validate-candidate`.  
Formal: `--help` · `validate` · `write` · `show` · `list-chapters`.  
Collab: `--help` · `write` · `validate` · `show`.

## Semantic build protocol

1. `$NARRATIVE_ARC_BUILD_CTL context --target <formal|collab> …` → `$ARC_CONTEXT`.
   It supplies full facts, Role, Domain, and registry. Missing context is a
   failure, not permission to fall back to a lens projection.
2. Build tree/group/leaf titles from the facts' substance story: objects,
   behaviors, contract surfaces, end-state, and verification. Topic is
   provenance only.
3. Order groups/leaves by Role `priority_tendency`, except where a fact
   dependency makes a prerequisite come first. Lens tags and registry
   relations govern membership and write-unit partitioning, not the document
   directory or titles.
4. Keep each top-level title to one through-line duty. Split or demote mixed
   duties; never glue titles for flow. Apply Domain `scannability` when
   splitting leaves or blocks; self-check the through-line against Domain
   `cognitive_frame` and `audience_type`.
5. Map each fact exactly once. Formal may explicitly use `excluded` or
   `unresolved`; collab candidates with either, or any unplaced fact, fail
   without overwriting the existing display arc.
6. `$NARRATIVE_ARC_BUILD_CTL validate-candidate --target <target> …` before
   persistence.

**Build prohibitions:** do not use registry lens order, Role priority, lens
tags/relations, or Role vocabulary as the presentation title schema; do not
force a fixed N-act package; do not glue top-level duties with 与/及/和,
`and`, or `&`; do not invent facts. A Formal `write_ready` candidate must not
contain a mapped fact with empty `lens_tags`.

**Formal:** build `mapped`, write/validate with `$NARRATIVE_ARC_CTL`; then
partition each leaf into valid lens chapters, write `write_ready`, and gate
with `--require-write-ready`.

**Collab:** build `status=display` with `tree + leaves[].fact_ids` only.
`validate-candidate` returns `$ARC_CANDIDATE_DIGEST`. Show the exact candidate
and that digest to the human. After explicit confirmation,
`$NARRATIVE_ARC_COLLAB_CTL write --file … --output-path … --digest
"$ARC_CANDIDATE_DIGEST" --confirm` rejects changed content, validates full
current-fact coverage, backs up an overwritten file, then writes.

## DONE / failure

- **DONE (Formal write/validate):** exit 0; path under active slice `_narrative-arc.json`.
- **DONE (collab write):** exit 0; backup + `fact_node_summary` when overwrite.
- **Failure:** non-zero (missing semantic context; invalid candidate; Formal path
  banned on collab; missing `--confirm` / `--output-path`).
