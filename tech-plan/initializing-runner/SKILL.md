---
name: initializing-runner
description: >-
  Autonomous Initializing step for tech-plan drafting. Reads template/meta from
  parent-provided raw sources, seeds the initial tech-doc with provenance tags and
  seeds the initial tech-doc with provenance tags, then returns control to the parent Initializing step.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside `tech-plan` Drafting.

## Scope

This skill is responsible for Step I1-I4 only:

1. Read the authoritative template and meta documents from parent-provided inputs.
2. Read the current cycle `decision-doc.md`.
3. Seed the first `tech-doc.md` draft from `Decision-Doc Mapping`.
4. Write seeded content with `[Source: ...]` tags.

Do not ask the user questions.
Do not perform InDialogue, Reopen, Evaluating, or delivery work here.

## Parent-Provided Inputs

The parent skill must inject these values before invoking this sub-skill:

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` — output paths are derived from this |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle decision doc |
| `$CYCLE_TYPE` | `topic` or `feature` — from parent dispatch; also used by `$RESOLVE_PLAN_ROLE` |
| `$CYCLE_ID` | Active cycle id (for `$RESOLVE_PLAN_ROLE`) |

Self-resolved at runtime (do not pass from parent):
- `$TECH_DOC_PATH` = `{REVISION_DIR}/tech-doc.md`

Load frameworks via `$FETCH_TECH_PLAN` and role constraints via `$RESOLVE_PLAN_ROLE` (see `../SKILL.md` → Command Index).

## Execution Contract

### Step I1 - Load mapping table and section registry

1. Run `$RESOLVE_PLAN_ROLE` with `$CYCLE_ID`; read stdout as Plan Scope Constraints and apply `### Role`.
2. Use `$FETCH_TECH_PLAN decision-doc-mapping`; read stdout as mapping markdown.
3. Locate the `## Decision-Doc Mapping` table.
4. Parse the mapping rows into:

```text
[
  { source, target, method, hard_constraint, notes }
]
```

5. Skip rows where `target` is `—`.
6. Use `$FETCH_TECH_PLAN section-registry`; parse stdout as JSON.
7. Read `document_preamble` for the tech-doc header block (substitute `{cycle_id}`, `{path}`, etc. at write time).
8. Initialize `fill_results` from `section_order` and `sections.{key}.heading`: each section gets a stable H2 line with section-key anchor, empty `content`, `status: "X"`. Do not use `document_skeleton`.

9. Mapping `target` values are registry **section keys** (e.g. keys in `section_order`). Validate each non-skipped target against the registry; reject unknown keys.

```text
fill_results[section_key] = {
  heading_line: "## {default_display} <!-- section-key:{section_key} -->",
  content: "",
  status: "X"
}
```

`default_display` = registry `sections.{key}.heading` at init (placeholder title; refiner may replace display text while preserving `<!-- section-key:… -->`).

Preserve `section_order` from the registry when rendering the final document.

### Step I2 - Prefetch decision-doc source content

1. Read `$DECISION_DOC_PATH`.
2. Collect the unique mapping `source` values from Step I1.
3. For each unique `source`, read the corresponding section or subsection content from the decision doc and store it in `source_cache[source]`.
4. If a source section is missing or empty, store `null` and continue without error.

Use the decision-doc section labels exactly as referenced by the mapping table, including nested selectors such as:

- `Direction Comparison > Excluded Directions`
- `Execution Analysis > Acceptance Criteria`
- `Execution Analysis > Implementation Sketch > Reversibility`
- `Assumptions & Risks - H-risk [待验证]`

### Step I3 - Apply each mapping row

For each mapping row:

```text
source_content = source_cache[source]
if source_content == null:
  continue
```

Apply the method as follows:

#### `Direct`

- Replace the target section body with `source_content`.
- Append `[Source: decision-doc.md#{source}]` at the end of the seeded content.
- If `hard_constraint: true`, also append `[Anchored: R0, by human]`.
- Set `fill_results[target].status = "I"`.

#### `Extract`

- Filter `source_content` according to `notes`.
- Keep only implementation-relevant material requested by the mapping row.
- If the extracted result is non-empty:
  - replace the target section body with the extracted content
  - append `[Source: decision-doc.md#{source}]` at the end
  - if `hard_constraint: true`, also append `[Anchored: R0, by human]`
  - set `fill_results[target].status = "I"`
- If the extracted result is empty, leave the original skeleton and keep status `X`.

#### `Transform`

- Start from empty section body (status `X`).
- Add one short context anchor using the source content:
  - prefer the first paragraph
  - otherwise use the first 200 characters
- Format the anchor as:

```markdown
> Initializing context anchor: <excerpt>
```

- Keep status `X`.

## Write Outputs

### Step I4 - Write tech doc

#### Write `$TECH_DOC_PATH`

Render the full tech document in registry `section_order`:

- write `document_preamble` first (with substituted placeholders)
- for each key in `section_order`: write `heading_line` then `fill_results[key].content`
- sections with status `X` and empty content may remain empty

## Expected Initial Seed Set

Derive seeded vs skeleton section **keys** from Step I3 results (`fill_results[*].status` is `I` vs `X`). Do not assume fixed section names — mapping rows and registry `section_order` define the actual set.

Transform rows keep status `X` (anchor only, empty or minimal body).

Do not hardcode section names during execution. Always derive from the mapping fetch (`decision-doc-mapping`) and section registry fetch (`section-registry`) in Step I1.

## Return Summary

After all writes succeed, return exactly this structure with the actual derived section keys:

```text
Initializing complete.
  Seeded (I): <space-separated section keys>
  Skeleton (X): <space-separated section keys>
  Next step: RoundIteration (Step 2)
```
