---
name: initializing-runner
description: >-
  Autonomous Initializing step for tech-plan drafting. Reads template/meta from
  parent-provided raw sources, seeds the initial tech-doc, writes section-progress.md
  and drafting-progress.md, then returns control to Scoping.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside `tech-plan` Drafting.

## Scope

This skill is responsible for Step I1-I4 only:

1. Read the authoritative template and meta documents from parent-provided inputs.
2. Read the current cycle `decision-doc.md`.
3. Seed the first `tech-doc.md` draft from `Decision-Doc Mapping`.
4. Write two separate progress files:
   - `section-progress.md` for `sections`
   - `drafting-progress.md` for `current_step`

Do not ask the user questions.
Do not perform Scoping, InDialogue, Reopen, Evaluating, or delivery work here.

## Parent-Provided Inputs

The parent skill must inject these values before invoking this sub-skill:

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` — output paths are derived from this |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle decision doc |
| `$CYCLE_TYPE` | `feature` or `topic` — selects `tpt_url` vs `shaping_tpt_url` in workflow-config.json |
| `$CYCLE_ID` | Active cycle id |

Self-resolved at runtime (do not pass from parent):
- `$TEMPLATE_PATH` — read `$WORKFLOW_DIR/workflow-config.json` → `tech-plan.tpt_url` (feature) or `tech-plan.shaping_tpt_url` (topic)
- `$META_PATH` — read `$WORKFLOW_DIR/workflow-config.json` → `tech-plan.tpt_meta_url`
- `$TECH_DOC_PATH` = `{REVISION_DIR}/tech-doc.md`
- `$SECTION_PROGRESS_PATH` = `{REVISION_DIR}/section-progress.md`
- `$DRAFTING_PROGRESS_PATH` = `{REVISION_DIR}/drafting-progress.md`

## Progress Templates

Load this template file from the skill repository at runtime. Do not embed its content inline.

| Template file | Output file |
|---|---|
| `$SKILL_ROOT/tech-plan/templates/section-progress.template.md` | `$SECTION_PROGRESS_PATH` |

## Execution Contract

### Step I1 - Load mapping table and template skeleton

1. Fetch and read the raw markdown at `$META_PATH`, via `gh api repos/{owner}/{repo}/contents/{path}?ref={ref}`.
2. Locate the `## Decision-Doc Mapping` table.
3. Parse the mapping rows into:

```text
[
  { source, target, method, notes }
]
```

4. Skip rows where `target` is `—`.
5. Fetch and read the raw markdown at `$TEMPLATE_PATH`, via `gh api repos/{owner}/{repo}/contents/{path}?ref={ref}`.
6. Parse the template into an ordered section map keyed by tech-doc section id:
   - top-level: `§1` ... `§10`
   - sub-sections where present: `§2.1`, `§2.2`, `§3.1`, etc.
7. Initialize `fill_results` from the template skeleton:

```text
fill_results[section_id] = {
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
- Set `fill_results[target].status = "I"`.

#### `Extract`

- Filter `source_content` according to `notes`.
- Keep only implementation-relevant material requested by the mapping row.
- If the extracted result is non-empty:
  - replace the target section body with the extracted content
  - set `fill_results[target].status = "I"`
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

### Step I4 - Write tech doc and two progress files

#### 1. Write `$TECH_DOC_PATH`

Render the full tech document in template order:

- preserve the template preamble/frontmatter
- preserve every heading
- use `fill_results[section_id].content` as the body for each parsed section
- leave untouched sections as their original skeleton

The output is the initialized draft:

- seeded sections contain decision-doc-derived content
- unseeded sections remain skeleton placeholders

#### 2. Write `$SECTION_PROGRESS_PATH`

Load `$SKILL_ROOT/tech-plan/templates/section-progress.template.md` as the write template.

Set `cycle_id` to `$CYCLE_ID`.

Populate `sections` using top-level section ids only.

Write each top-level `§N` status from the initialized result set as `I` or `X`, consistent with the parent skill's top-level section-key model.

Do not write subsection keys into `section-progress.md` during Initializing.
Do not populate `na_evidence` or `reopen_reasons` here.

#### 3. Write `$DRAFTING_PROGRESS_PATH`

Write directly:

```yaml
---
version: 1
cycle_id: {CYCLE_ID}
current_step: Scoping
---
```

## Expected Initial Seed Set

When the current mapping table matches the known tech-plan meta, the initialized draft typically seeds:

- `§2.1`
- `§2.2`
- `§2.3`
- `§2.4`
- `§2.5`
- `§3.1`
- `§3.3`
- `§5.3`
- `§8.2`
- `§9.1`

Sections such as `§1`, `§3.2`, `§4`, `§5.1`, `§5.2`, `§6`, `§7`, `§8.1`, `§9.2`, `§9.3`, `§9.4`, and `§10` remain skeleton-first unless the template or mapping changes.

Do not hardcode these ids during execution. Always derive the actual result from `$META_PATH` and `$TEMPLATE_PATH`.

## Return Summary

After all writes succeed, return exactly this structure with the actual derived section ids:

```text
Initializing complete.
  Seeded (I): <space-separated seeded section ids>
  Skeleton (X): <space-separated skeleton section ids>
  Next step: Scoping
```

