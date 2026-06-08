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
| `$TEMPLATE_PATH` | Raw markdown source for the tech-doc template (`tpt_url`) |
| `$META_PATH` | Raw markdown source for the tech-plan meta rules (`tpt_meta_url`) |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle decision doc |
| `$TECH_DOC_PATH` | Absolute output path for `revision{N}/tech-doc.md` |
| `$SECTION_PROGRESS_PATH` | Absolute output path for `revision{N}/section-progress.md` |
| `$DRAFTING_PROGRESS_PATH` | Absolute output path for `revision{N}/drafting-progress.md` |
| `$CYCLE_ID` | Active cycle id |

`$TEMPLATE_PATH` and `$META_PATH` are source-of-truth inputs from the parent. Treat them as remote/raw content locations, not as local repo-relative fallbacks.

## Embedded Progress Templates

Use these embedded templates exactly as the write format. Do not load separate local template files at runtime.

### `drafting-progress.md`

```markdown
---
version: 1
cycle_id: "{cycle_id}"
current_step: Ready
# State machine ref: lulu-dev-workflow/tech-plan/templates/drafting-state-machine.json
---
```

### `section-progress.md`

```markdown
---
version: 1
cycle_id: "{cycle_id}"
# Legend ref: lulu-dev-workflow/tech-plan/templates/20-tech-plan-spec-meta.md → ## Section Status Legend
# Section statuses: X | I | N/A-s | N/A-c | D | V | ! | S
# I     = seeded from decision-doc (Initializing) or re-opened by user (Reopen); has content, needs dialogue confirmation
# X     = skeleton placeholder only, no content yet
# N/A-s = not applicable: excluded by change type (structural)
# N/A-c = not applicable: excluded by decision-doc content analysis (content)
# !     = expired: user triggered Reopen on an upstream section; must re-review
sections:
  §1: X
  §2: X
  §3: X
  §4: X
  §5: X
  §6: X
  §7: X
  §8: X
  §9: X
  §10: X
# na_evidence: citable source for each N/A determination (populated by scoping-runner)
# Keys are sub-section granularity (e.g. §1.3, §4.5); top-level section status derived from strictest sub-section.
# N/A-s example: "Intent: 'add new feature' — keyword 'bugfix' or 'refactor' not found"
# N/A-c example: "decision-doc §Scope: 'no API contract changes; internal data layer only'"
na_evidence: {}
# reopen_reasons: populated when user triggers Reopen
# §N (re-opened section): user's stated reason
# downstream sections: "reopened: §N — <§N section title>"
reopen_reasons: {}
---
```

## Execution Contract

### Step I1 - Load mapping table and template skeleton

1. Fetch and read the raw markdown at `$META_PATH`.
2. Locate the `## Decision-Doc Mapping` table.
3. Parse the mapping rows into:

```text
[
  { source, target, method, notes }
]
```

4. Skip rows where `target` is `—`.
5. Fetch and read the raw markdown at `$TEMPLATE_PATH`.
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

Start from the embedded `section-progress.md` template.

Set `cycle_id` to `$CYCLE_ID`.

Populate `sections` using top-level section ids only.

Write each top-level `§N` status from the initialized result set as `I` or `X`, consistent with the parent skill's top-level section-key model.

Do not write subsection keys into `section-progress.md` during Initializing.
Do not populate `na_evidence` or `reopen_reasons` here.

#### 3. Write `$DRAFTING_PROGRESS_PATH`

Start from the embedded `drafting-progress.md` template.

Set:

- `cycle_id: $CYCLE_ID`
- `current_step: Scoping`

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

