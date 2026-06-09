---
name: generating-runner
description: >-
  Autonomous Generating step for tech-plan drafting. Scans tech-doc for §state:X
  sections, generates content for each from decision-doc context, writes §state:P
  provenance comments, advances drafting-progress.md to FreeEdit, and returns
  control to the parent skill.
---

# generating-runner

✅ Verified: Run this sub-skill only for the `Generating` step inside `tech-plan` Drafting.

## Scope

✅ Verified: This skill is responsible for Step G1-G4 only:

1. Scan `tech-doc.md` for all sections marked `<!-- §state:X -->`.
2. Generate content for each X section from decision-doc context and existing I/P sections.
3. Write generated content and replace `<!-- §state:X -->` with `<!-- §state:P -->` in tech-doc.
4. Write `drafting-progress.md` with `current_step: FreeEdit`.

✅ Verified: Do not ask the user questions.  
✅ Verified: Do not perform Initializing, Scoping, FreeEdit, or delivery work here.

## Parent-Provided Inputs

✅ Verified: The parent skill must inject these values before invoking this sub-skill:

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` — TECH_DOC_PATH and DRAFTING_PROGRESS_PATH are derived from this |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle `decision-doc.md` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved at runtime:
- `$TECH_DOC_PATH` = `{REVISION_DIR}/tech-doc.md`
- `$DRAFTING_PROGRESS_PATH` = `{REVISION_DIR}/drafting-progress.md`

## Hard Constraint: Context-Grounded Generation

✅ Verified: Every generated section must be grounded in one or more of:

- Content from `$DECISION_DOC_PATH` (primary source)
- Content from sections already marked `<!-- §state:I -->` or `<!-- §state:P -->` in tech-doc (inferred context)
- The section's own skeleton/placeholder text (structural guidance)

✅ Verified prohibition:

- Do not fabricate facts not derivable from the above sources.
- If context is genuinely insufficient for a section, generate best-effort content from available context; do not leave `<!-- §state:X -->` in the final output.

## Execution Contract

### Step G1 - Load inputs

✅ Verified:

1. Read `$TECH_DOC_PATH` and collect all sections whose provenance comment is `<!-- §state:X -->`:

```text
x_sections = [
  { section_id, heading, skeleton_body }
]
```

2. Read `$DECISION_DOC_PATH` and store full content as `decision_doc_content`.
3. Read all sections marked `<!-- §state:I -->` or `<!-- §state:P -->` in tech-doc and store as `seeded_context`.

### Step G2 - Generate content

✅ Verified: For each entry in `x_sections`:

```text
for each { section_id, heading, skeleton_body } in x_sections:
  derive content from: decision_doc_content + seeded_context + skeleton_body
  generated_content = <AI-generated body for this section>
  generation_results[section_id] = { status: "P", content: generated_content }
```

✅ Verified rules:

- Process sections in template order.
- Each previously generated section (`P`) may be used as additional context for subsequent sections.
- Do not ask the user for clarification; always generate best-effort content.

### Step G3 - Write tech-doc

✅ Verified: For each entry in `generation_results` with `status: "P"`:

1. In `$TECH_DOC_PATH`, replace `<!-- §state:X -->` above the section heading with `<!-- §state:P -->`.
2. Replace the section body with `generated_content`.

✅ Verified write discipline:

- Write each section atomically (comment + body together).
- Do not modify sections marked `<!-- §state:I -->`, `<!-- §state:N/A-s -->`, or `<!-- §state:N/A-c -->`.

### Step G4 - Write drafting-progress

✅ Verified: Write `$DRAFTING_PROGRESS_PATH`:

```yaml
---
version: 1
cycle_id: {CYCLE_ID}
current_step: FreeEdit
---
```

## Return Summary

✅ Verified: After all writes succeed, return exactly this structure with the actual derived ids:

```text
Generating complete.
  Generated (P): <space-separated section ids>
  Next step: FreeEdit
```
