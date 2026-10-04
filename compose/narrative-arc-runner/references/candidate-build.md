# Candidate build

Produce the narrative arc and write it to `OUTPUT_PATH`.

Build Mapped, then Split, then Check, then Write.

## Script Macros

- `$NARRATIVE_ARC_BUILD` — `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_build_control.py"`.
- `$NARRATIVE_ARC_CTL` — `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"`.

## Context

Read the build input before any outline choice.

- `$NARRATIVE_ARC_BUILD context …` → `$ARC_CONTEXT`: facts, Role, Domain, and registry.
- Missing context fails the build. Do not fall back to a lens projection.
- Re-read Role `priority_tendency` and Domain `expression_conventions.scannability` from `$ARC_CONTEXT` before Mapped.

## Principles

Who each build choice listens to, and how hard that bind is.

| Decision | Listen to | Hardness |
|---|---|---|
| Group/leaf **titles and grouping shape** | Substance story in facts (objects, behaviors, contract surfaces, end-state, verification, …) | **Must** |
| Group/leaf **order** | Role `priority_tendency` | **Must** (exception: fact dependency forces prerequisite first) |
| **Intra-tier order** (groups tied in one `priority_tendency` slot) | Descending narrative altitude: whole before its parts | **Should** (tie-breaker; explicit Role order or fact dependency overrides) |
| Fact membership + phase-2 write-unit split | The fact's lens + registry lens relations | **Must** — never whole-document leaf order; never the presentation title schema |
| Split / do not mix | Domain `expression_conventions.scannability` (full text for active profile) | **Must** |
| Genre mission / through-line check | Domain `cognitive_frame` / `audience_type` | **Must** (enforced by Check) |

## Mapped

Where each fact sits, and what that station is named.

### Where

- A composite or pending-split fact goes to `excluded`, or to `unresolved` when blocked.
- A top title is a through-line station. Demote a leaf-level concern to a child.
- A child is strictly narrower than its parent. Siblings sit at a comparable altitude.
- After the shape is set, flow may only reorder. Flow does not split or merge.

### Name

- One top title carries one duty. Do not glue duties with 与/及/和, `and`, or `&`.
- A title below the roots names a station: an object, a surface, or a behavior area. It does not compress a fact claim. Claims stay in the content.
- Related aspects may be paired. An assertion chain is replaced by the name of their shared object.
- Titles do not come from registry lens order, Role priority, a fact's lens, or Role vocabulary.

## Split

Split each leaf into chapters by lens. Start from the mapped tree.

- This candidate is `status=write_ready`. It is the arc.

## Check

Run every item. Any hit: reorganize, split again, then check again. Do not persist a failing candidate.

- Lens catalog: every top group, or nearly every one, is a single lens. A business-sounding title does not exempt. Splitting one lens into several pure groups does not exempt.
- Fact list: most leaves hold one fact under a title that restates that fact. Regroup around a shared object, behavior, or end-state.
- Glued tops: a top title joins duties with 与/及/和, `and`, or `&`, or too many tops read as leaf concerns. Split or demote.
- Claim titles: a title below the roots states a fact claim or an assertion chain. Rename it to a station, or merge same-object siblings.
- Scannability: one leaf mixes what Domain `scannability` keeps apart. Split.
- Order: group/leaf order does not follow Role `priority_tendency`, or a chapter comes before a chapter its facts depend on. Redo Mapped or Split.
- Through-line: the outline drifts from Domain `cognitive_frame`, or is not a reviewable through-line for `audience_type`. Thicken the opening when needed. Do not force a fixed N-act directory.

## Write

After Check is clear, write the `write_ready` candidate to `OUTPUT_PATH`.

1. `$NARRATIVE_ARC_CTL write --revision-dir … --file <candidate> --output-path "$OUTPUT_PATH" --require-write-ready`
2. After success, delete the temporary candidate files.

