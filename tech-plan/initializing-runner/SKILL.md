---
name: initializing-runner
description: >-
  Autonomous Initializing step for tech-plan drafting. Reads template/meta from
  parent-provided raw sources, seeds the initial tech-doc with §state provenance
  comments, writes drafting-progress.md, then returns control to L1Scaffold.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside `tech-plan` Drafting.

## Scope

This skill is responsible for Step I1-I4 only:

1. Read the authoritative template and meta documents from parent-provided inputs.
2. Read the current cycle `decision-doc.md`.
3. Seed the first `tech-doc.md` draft from `Decision-Doc Mapping`.
4. Write provenance comment `§state:I` or `§state:X` above each section heading in tech-doc.

Do not ask the user questions.
Do not perform InDialogue, Reopen, Evaluating, or delivery work here.

## Parent-Provided Inputs

The parent skill must inject these values before invoking this sub-skill:

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` — output paths are derived from this |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle decision doc |
| `$CYCLE_TYPE` | `feature` or `topic` — selects `tpt_v2_url` (feature) vs `shaping_tpt_url` (topic) in workflow-config.json |
| `$CYCLE_ID` | Active cycle id |

Self-resolved at runtime (do not pass from parent):
- `$TEMPLATE_SECTION` = `tech-plan`
- `$TEMPLATE_KEY` — `tpt_v2_url` (feature) or `shaping_tpt_url` (topic)
- `$META_KEY` — `tpt_meta_v2_url` (feature) or `tpt_meta_url` (topic)
- `$TECH_DOC_PATH` = `{REVISION_DIR}/tech-doc.md`
- `$DRAFTING_PROGRESS_PATH` = `{REVISION_DIR}/drafting-progress.md`

Load templates via the shared entry (see `../_runtime.md` → Template Fetch):

```text
Use $FETCH_TEMPLATE tech-plan $META_KEY
```

Replace `$META_KEY` with `$TEMPLATE_KEY` for the template skeleton fetch.

## Execution Contract

### Step I1 - Load mapping table and template skeleton

1. Use `$FETCH_TEMPLATE tech-plan $META_KEY`; read stdout as meta markdown.
2. Locate the `## Decision-Doc Mapping` table.
3. Parse the mapping rows into:

```text
[
  { source, target, method, hard_constraint, notes }
]
```

4. Skip rows where `target` is `—`.
5. Use `$FETCH_TEMPLATE $TEMPLATE_SECTION $TEMPLATE_KEY`; read stdout as template markdown.
6. Parse the template into an ordered section map keyed by section heading name (e.g. `North Star`, `Non-Goals`, `Invariants`, `Key Decisions`, `Approach Skeleton`, `Tasks`).
7. Initialize `fill_results` from the template skeleton:

```text
fill_results[section_name] = {
  heading: <original heading line>,
  content: <original template body>,
  status: "X"
}
```

Preserve the original template order and untouched sections exactly as they appear in the template.

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
- Set `fill_results[target_name].status = "I"`.

#### `Extract`

- Filter `source_content` according to `notes`.
- Keep only implementation-relevant material requested by the mapping row.
- If the extracted result is non-empty:
  - replace the target section body with the extracted content
  - append `[Source: decision-doc.md#{source}]` at the end
  - if `hard_constraint: true`, also append `[Anchored: R0, by human]`
  - set `fill_results[target_name].status = "I"`
- If the extracted result is empty, leave the original skeleton and keep status `X`.

#### `Transform`

- Keep the original template skeleton in place.
- Add one short context anchor above the untouched skeleton body using the source content:
  - prefer the first paragraph
  - otherwise use the first 200 characters
- Format the anchor as:

```markdown
> Initializing context anchor: <excerpt>
```

- Keep status `X`.

## Write Outputs

### Step I4 - Write tech doc and progress file

#### 1. Write `$TECH_DOC_PATH`

Render the full tech document in template order:

- preserve the template preamble/frontmatter
- preserve every heading
- immediately above each section heading, insert the provenance comment:
  - `fill_results[section_name].status = "I"` → `<!-- §state:I -->`
  - `fill_results[section_name].status = "X"` → `<!-- §state:X -->`
- use `fill_results[section_name].content` as the body for each parsed section
- leave untouched sections as their original skeleton

After rendering all sections, derive the initial State Vector from `fill_results`:
- `status: "I"` → `L1`; `status: "X"` → `L0`
- Map to the 6 dimensions: `NS`, `NG`, `INV`, `KD`, `SK`, `T`
- Section → dimension: `North Star` → `NS`; `Non-Goals` → `NG`; `Invariants` → `INV`; `Key Decisions` → `KD`; `Approach Skeleton` → `SK`; `Tasks` → `T`
- Update the `<!-- state-vector: ... -->` comment in the document header.

Example result:
```
<!-- state-vector: NS:L0, NG:L1, INV:L1, KD:L1, SK:L1, T:L1 -->
```

#### 2. Write `$DRAFTING_PROGRESS_PATH`

Write directly:

```yaml
---
version: 1
cycle_id: {CYCLE_ID}
current_step: L1Scaffold
---
```

## Expected Initial Seed Set

When the current mapping table matches the v2 meta, the initialized draft typically seeds:

- `Invariants` (Known Constraints, H-risk 已验证)
- `Key Decisions` (Decision Rationale, Excluded Directions, H-risk 待验证)
- `Approach Skeleton` (External Dependencies, Reversibility)
- `Tasks` (Acceptance Criteria)

Sections that remain skeleton-first: `North Star`, `Non-Goals` (Transform method keeps status X).

Do not hardcode these names during execution. Always derive the actual result from the meta and template fetches in Step I1.

## Return Summary

After all writes succeed, return exactly this structure with the actual derived section ids:

```text
Initializing complete.
  Seeded (I): <space-separated seeded section names>
  Skeleton (X): <space-separated skeleton section names>
  State Vector: NS:L? NG:L? INV:L? KD:L? SK:L? T:L?
  Next step: L1Scaffold
```

