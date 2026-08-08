---
name: narrative-arc-runner
description: >-
  Compose semantic narrative-arc builder. Init writes Formal arcs
  (_narrative-arc.json) inline; G2 requests collaboration display arcs
  (write + Viewer mount).
---

# narrative-arc-runner

Use when a compose caller **declares** this skill to build a Formal or collab
narrative arc. Collab ≠ Formal file.

**Must:** obtain full build context via `$NARRATIVE_ARC_BUILD_CTL`; build from
facts' substance story; pass the pre-persist self-check; then validate and
persist with the target control.  
**Must not:** use topic / old arc / lens order as the narrative spine; use
lens clusters; persist a candidate that failed or skipped the pre-persist
self-check; write Formal from collab control; auto-write collab without
full semantic context and candidate validation.

## Dual entry

| Entry | Caller | Input | Done when |
|-------|--------|----------|-----------|
| `target=formal` | `initializing-runner` | Init context | Formal `write_ready` / Init contract |
| `target=collab` | G2 Topic Loop | Collab Input below | Summary; Viewer mount on success |

### Collab Input (subagent)

```text
target: collab
INDUCTIVE_OUT_DIR: <revision dir>
PROJECT_ROOT: <abs project root>
COMPOSE_PROFILE: <profile id>
CYCLE_ID: <cycle id>
OUTPUT_PATH: _narrative-arc.collab.json
```

Do **not** paste fact bodies in the Task prompt — read from disk via `context`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$NARRATIVE_ARC_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_build_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$NARRATIVE_ARC_COLLAB_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_collab_control.py"` |
| `$COMPOSE_VIEWER_CTL` | `python3 "$SKILL_ROOT/compose/compose-viewer/scripts/compose_viewer_control.py"` |

Build: `--help` · `context` · `validate-candidate`.  
Formal: `--help` · `validate` · `write` · `show` · `list-chapters`.  
Collab: `--help` · `write` · `validate` · `show`.

## Semantic build protocol

One cognition for both targets; `formal` and `collab` differ only in
persistence and phase gates (below).

1. `$NARRATIVE_ARC_BUILD_CTL context --target <formal|collab> …` → `$ARC_CONTEXT`.
   It supplies full facts, Role, Domain, and registry. Missing context is a
   failure, not permission to fall back to a lens projection. Re-read Role
   `priority_tendency` and Domain `expression_conventions.scannability` from
   `$ARC_CONTEXT` before building.
2. **Listen-who (arc build):**

   | Decision | Listen to | Hardness |
   |---|---|---|
   | Group/leaf **titles and grouping shape** | Substance story in facts (objects, behaviors, contract surfaces, end-state, verification, …) | **Must** |
   | Group/leaf **order** | Role `priority_tendency` | **Must** (exception: fact dependency forces prerequisite first) |
   | **Intra-tier order** (groups tied in one `priority_tendency` slot) | Descending narrative altitude: whole before its parts | **Should** (tie-breaker; explicit Role order or fact dependency overrides) |
   | Fact membership + Formal phase-2 write-unit split | Lens tags + registry lens relations | **Must** — never whole-document leaf order; never the presentation title schema |
   | Split / do not mix | Domain `expression_conventions.scannability` (full text for active profile) | **Must** |
   | Genre mission / through-line check | Domain `cognitive_frame` / `audience_type` | **Must** (enforced by step 5) |

3. Build the tree from the facts' substance story; topic is provenance only.
   Optional `tree` packaging, depth unrestricted. Map each fact exactly once.
   Formal: composite / pending-split facts → `excluded` (or `unresolved` if
   blocked); collab candidates with either bucket, or any unplaced fact, fail
   without overwriting the existing display arc.
4. **Top-level title discipline** (`tree` roots only):

   | Principle | Rule |
   |---|---|
   | Single duty | One chapter duty per top title. Never glue duties with 与/及/和, `and`, or `&`. |
   | Chapter altitude | Top level = through-line chapter stations only. Demote leaf-level concerns to children. |
   | Flow | After shape is set, reorder only. Flow never decides split/merge. |

   Conflict exits: overflow → child under a single-duty parent; never glue
   for flow; never merge unequal altitudes to shorten the path.

   **Non-top title discipline** (all titles below `tree` roots):

   | Principle | Rule |
   |---|---|
   | Name, don't assert | Title = station name (object, surface, behavior area), never a compressed fact claim; claims live in content. |
   | No claim chains | Pairing related aspects is fine; chaining assertions is not — name their shared object instead. |
   | Altitude nesting | Child strictly narrower than parent; siblings at comparable altitude. |
5. **Pre-persist self-check (hard gate).** Run every item; any hit → rebuild
   titles/shape and re-run this step. Never persist a failing candidate.
   - **Lens-catalog detector:** list each top-level group's member-fact lens
     set. All (or nearly all) groups single-lens-pure → the tree is a lens
     projection with laundered titles → rebuild. Business-sounding titles do
     not exempt; splitting one lens into several pure groups does not exempt.
   - **Mapping-not-narrative detector:** a majority of leaves each holding
     one fact under a title that restates that fact → this is fact mapping,
     not narrative building → regroup leaves around shared objects,
     behaviors, and end-states.
   - Top titles glued with 与/及/和 (or `and`/`&`), or too many tops that
     read as leaf concerns → split or demote (title discipline above).
   - Non-top titles reading as fact claims or assertion chains → rename to
     station names, or merge same-object siblings (non-top discipline above).
   - Single-leaf mix that violates Domain `scannability` → split.
   - Order inverted vs `priority_tendency` with no fact-dependency reason →
     reorder.
   - Outline drifted from Domain `cognitive_frame`, or not a reviewable
     through-line for `audience_type` → fix (thicken opening info if needed;
     do not force a fixed N-act directory).

   Collab: record the outcome in the candidate's `meta.note`, e.g.
   `self-check: lens-catalog=clear; grouping=narrative`.
6. `$NARRATIVE_ARC_BUILD_CTL validate-candidate --target <target> …` before
   persistence. Machine validation gates structure and coverage only — it
   cannot detect a lens catalog; that is what step 5 exists for.

**Build prohibitions:** do not use registry lens order, Role priority, lens
tags/relations, or Role vocabulary as the presentation title schema — Role
`priority_tendency` orders groups/leaves and never generates titles or a
mandatory top count; lens relations guide argumentation within content, not
the visible directory. Do not force background / analysis / solution — or any
fixed N-act label set — as the **only** allowed top-level packaging (reading
aids OK); do not glue top-level duties with 与/及/和, `and`, or `&`; do not
invent facts. A Formal `write_ready` candidate must not contain a mapped fact
with empty `lens_tags`, and each chapter `lens` must be ∈ that fact's
`lens_tags`.

**Formal:** build `mapped`, write/validate with `$NARRATIVE_ARC_CTL`; then
partition each leaf into valid lens chapters, write `write_ready`, and gate
with `--require-write-ready`.

**Collab (independent completion):** `context` → semantic build
`status=display` with `tree + leaves[].fact_ids` only → **pre-persist
self-check (step 5)** → `validate-candidate` → `$NARRATIVE_ARC_COLLAB_CTL
write --file … --output-path "$OUTPUT_PATH" --digest …` →
`$COMPOSE_VIEWER_CTL mount --revision-dir "$INDUCTIVE_OUT_DIR" --arc-file
"$OUTPUT_PATH"` → delete temporary transport file → return summary.
No human confirm gate after validate. Digest only proves the validated bytes
were not altered before write — it does not replace step 5.

## DONE / failure

### Collab subagent summary (return exactly this shape)

```text
status: done|failed
target: collab
output_path: <OUTPUT_PATH>
wrote: true|false
mounted: true|false
viewer_url: <url or empty>
error: <empty or message>
```

- **DONE (collab):** `wrote=true` · `mounted=true` · non-empty `viewer_url` (mount stdout).
- **Partial (collab):** `wrote=true` · `mounted=false` — new arc on disk; do not claim Viewer updated.
- **FAIL (collab validate/write):** `wrote=false` · `mounted=false` — existing display arc unchanged.
- **DONE (Formal write/validate):** exit 0; path under active slice `_narrative-arc.json`.
- **Failure:** non-zero script exit (missing semantic context; invalid candidate; Formal path
  banned on collab; missing digest / `--output-path`).
