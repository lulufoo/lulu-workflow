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

Mandatory constraints on each build choice.

- Group and leaf titles, and the grouping shape, come from the substance story in the facts.
- Group and leaf order follows Role `priority_tendency`. A fact dependency places the prerequisite first.
- Fact membership and the chapter split follow lens tags and registry lens relations. Do not order the document as a leaf list. Do not use lens relations as the title schema.
- Split or keep together according to the full Domain `expression_conventions.scannability` for the active profile.
- The through-line follows Domain `cognitive_frame` and `audience_type`.



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
- Titles do not come from registry lens order, Role priority, lens tags, or Role vocabulary.



## Split

Split each leaf into chapters by lens. Start from the mapped tree.

- This candidate is `status=write_ready`. It is the arc.



## Check

- Lens catalog: every top group, or nearly every one, is a single lens.
- Fact list: most leaves hold one fact under a title that restates that fact.
- Any hit: reorganize, then check again.



## Write

After Check is clear, write the `write_ready` candidate to `OUTPUT_PATH`.

1. `$NARRATIVE_ARC_CTL write --revision-dir … --project-root … --file <candidate> --output-path "$OUTPUT_PATH" --require-write-ready`
2. After success, delete the temporary candidate files.

