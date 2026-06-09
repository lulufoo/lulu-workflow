---
name: scoping-runner
description: >-
  Autonomous Scoping step for tech-plan drafting. Evaluates conditional sections
  for N/A-s or N/A-c using embedded section conditions, writes §state provenance
  comments into tech-doc, advances drafting-progress.md to Generating, and
  returns control to the parent skill.
---

# scoping-runner

✅ Verified: Run this sub-skill only for the `Scoping` step inside `tech-plan` Drafting.

## Scope

✅ Verified: This skill is responsible for Step S1-S4 only:

1. Load the embedded conditional-section rules and decision-doc intent.
2. Run Pass 1 structural scanning and Pass 2 content scanning.
3. Write `§state:N/A-s` or `§state:N/A-c` provenance comments into tech-doc.
4. Write `drafting-progress.md` with `current_step: Generating`.

✅ Verified: Do not ask the user questions.  
✅ Verified: Do not perform Initializing, Generating, FreeEdit, or delivery work here.

## Parent-Provided Inputs

✅ Verified: The parent skill must inject these values before invoking this sub-skill:

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` — TECH_DOC_PATH and DRAFTING_PROGRESS_PATH are derived from this |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle `decision-doc.md` |

Self-resolved at runtime:
- `$META_KEY` = `tpt_meta_url` (section `tech-plan`)
- `$TECH_DOC_PATH` = `{REVISION_DIR}/tech-doc.md`
- `$DRAFTING_PROGRESS_PATH` = `{REVISION_DIR}/drafting-progress.md`

Load section conditions via `fetch_template.py` (see `../_runtime.md` → Template Fetch).

## Authoritative References

### Section Conditions

Self-read at Step S1: run `fetch_template.py --section tech-plan --key tpt_meta_url`; read `## Section Conditions` table from stdout. This is the execution source of truth — do not use any embedded snapshot.

## Hard Constraint: Verifiable N/A Determination

✅ Verified: Every N/A assignment must be backed by a directly citable source.

- ✅ Verified: `N/A-s` must cite the exact `**Intent:** "<intent text>"` line from the decision doc and state which trigger keyword was not found.
- ✅ Verified: `N/A-c` must cite a verbatim passage from the referenced decision-doc section that positively shows the condition is absent.

✅ Verified prohibition:

- Do not mark a section N/A on the basis of "not mentioned in decision-doc" alone.
- Absence of mention does not prove non-applicability.

## Execution Contract

### Step S1 - Load determination inputs

✅ Verified:

1. Run `fetch_template.py --section tech-plan --key tpt_meta_url`; read `## Section Conditions` table from stdout and extract all conditional sections.
2. Partition the rows by `Trigger Type`:
   - `structural_list`: all rows where `Trigger Type = structural`
   - `content_list`: all rows where `Trigger Type = content`
3. Read `$DECISION_DOC_PATH` and extract the full `**Intent:**` line text for Pass 1.
4. Initialize:

```text
na_results = {}
subsection_statuses = {}
```

✅ Verified: `na_results` is keyed by conditional subsection id and stores both the assigned N/A status and the citable evidence.

### Step S2 - Pass 1: structural scan

✅ Verified: For each row in `structural_list`:

```text
for each {section, trigger, evidence_source} in structural_list:
  inspect the extracted Intent text only
  if the required keyword is not present:
    na_results[section_id] = {
      status: "N/A-s",
      evidence: "Intent: '<intent text>' - keyword '<keyword>' not found"
    }
    subsection_statuses[section_id] = "N/A-s"
  else:
    subsection_statuses[section_id] = "X"
```

✅ Verified rules:

- This pass is purely string matching against the `**Intent:**` line.
- Do not read decision-doc body content during Pass 1.
- Structural matches are repeatable and deterministic from the same intent text.
- A matched structural trigger means the subsection remains applicable and will be processed by generating-runner as unresolved `X`.

### Step S3 - Pass 2: content scan

✅ Verified: For each row in `content_list`:

```text
for each {section, trigger, evidence_source} in content_list:
  locate the referenced decision-doc section(s) named by evidence_source
  search for positive denying evidence that the trigger condition does not apply
  if found:
    na_results[section_id] = {
      status: "N/A-c",
      evidence: "\"<verbatim passage>\" (decision-doc <section reference>)"
    }
    subsection_statuses[section_id] = "N/A-c"
  else:
    subsection_statuses[section_id] = "X"
```

✅ Verified rules:

- Only assign `N/A-c` when the decision doc contains a positively citable statement that denies applicability.
- If no such statement is found, keep the subsection applicable for generating-runner as unresolved `X`. Do not infer `N/A-c` from silence.
- The `evidence_source` field defines where the scan must look first; do not search unrelated sections as substitutes.

### Step S4 - Write outputs

✅ Verified: For each entry in `na_results`:

1. In `$TECH_DOC_PATH`, locate the section heading for the matched section. Replace its `<!-- §state:X -->` comment with the appropriate provenance comment:

```markdown
<!-- §state:N/A-s evidence:"Intent: '<intent text>' — keyword '<keyword>' not found" -->
```

or

```markdown
<!-- §state:N/A-c evidence:"'<verbatim passage>' (decision-doc <section>)" -->
```

2. Update `$DRAFTING_PROGRESS_PATH`:
   - set `current_step: Generating`

✅ Verified write discipline:

- `drafting-progress.md` is the only progress file written by this sub-skill; it must end at `Generating`.
- Do not write any separate progress or evidence files.

## Return Summary

✅ Verified: After all writes succeed, return exactly this structure with the actual derived ids:

```text
Scoping complete.
  N/A-s (structural): <space-separated subsection ids>
  N/A-c (content): <space-separated subsection ids>
  Remaining (X): <space-separated unresolved section ids>
  Next step: Generating
```
