---
name: scoping-runner
description: >-
  Autonomous Scoping step for tech-plan drafting. Evaluates conditional sections
  for N/A-s or N/A-c using embedded section conditions, writes N/A reasons into
  the tech doc, updates section-progress.md, advances drafting-progress.md to
  InDialogue, and returns control to the parent skill.
---

# scoping-runner

✅ Verified: Run this sub-skill only for the `Scoping` step inside `tech-plan` Drafting.

## Scope

✅ Verified: This skill is responsible for Step S1-S4 only:

1. Load the embedded conditional-section rules and decision-doc intent.
2. Run Pass 1 structural scanning and Pass 2 content scanning.
3. Write N/A evidence into the tech doc and `section-progress.md`.
4. Write `drafting-progress.md` with `current_step: InDialogue`.

✅ Verified: Do not ask the user questions.  
✅ Verified: Do not perform Initializing, InDialogue, Reopen, Extending, Checking, or delivery work here.

## Parent-Provided Inputs

✅ Verified: The parent skill must inject these values before invoking this sub-skill:

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` — TECH_DOC_PATH, SECTION_PROGRESS_PATH, and DRAFTING_PROGRESS_PATH are derived from this |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle `decision-doc.md` |

Self-resolved at runtime:
- `$META_PATH` — read `$WORKFLOW_DIR/workflow-config.json` → `tech-plan.tpt_meta_url`; fetch that URL to get `## Section Conditions`
- `$TECH_DOC_PATH` = `{REVISION_DIR}/tech-doc.md`
- `$SECTION_PROGRESS_PATH` = `{REVISION_DIR}/section-progress.md`
- `$DRAFTING_PROGRESS_PATH` = `{REVISION_DIR}/drafting-progress.md`

## Authoritative References

### Section Conditions

Self-read at Step S1: `$WORKFLOW_DIR/workflow-config.json` → `tech-plan.tpt_meta_url`; fetch that URL and read `## Section Conditions` table. This is the execution source of truth — do not use any embedded snapshot.

### Section Status Symbols

Read inline comments in `$SKILL_ROOT/tech-plan/templates/section-progress.template.md`.

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

1. Read `$WORKFLOW_DIR/workflow-config.json` → `tech-plan.tpt_meta_url`; fetch that URL; read `## Section Conditions` table and extract all conditional sections.
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
- A matched structural trigger means the subsection remains applicable and should continue to InDialogue as unresolved, not `V`.

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
- If no such statement is found, keep the subsection applicable for later dialogue as unresolved `X`. Do not infer `N/A-c` from silence.
- The `evidence_source` field defines where the scan must look first; do not search unrelated sections as substitutes.

### Step S4 - Write outputs

✅ Verified: For each entry in `na_results`:

1. Write an N/A banner at the start of the matching section body in `$TECH_DOC_PATH`:

```markdown
> N/A-s: <evidence>
```

or

```markdown
> N/A-c: "<cited passage>" (decision-doc <section>)
```

2. Update `$SECTION_PROGRESS_PATH`:
   - `na_evidence[<subsection id>] = <cited source>`
   - `sections[§N] = <aggregated top-level status>` using the aggregation rule block below
3. Update `$DRAFTING_PROGRESS_PATH`:
   - set `current_step: InDialogue`

✅ Verified write discipline:

- `section-progress.md` is the only progress file that records `sections` and `na_evidence`.
- `drafting-progress.md` is the only progress file that records the step machine and must end this sub-skill at `InDialogue`.
- Do not write subsection keys under `sections`.

## Top-Level Section Aggregation Rule Block

✅ Verified: `section-progress.md` keeps top-level keys only in `sections`:

```text
§1 ... §10
```

✅ Verified: Subsection-granularity N/A evidence must be written under `na_evidence`, for example:

```text
na_evidence["§1.3"] = "Intent: '...' - keyword 'bugfix' not found"
na_evidence["§9.4"] = "\"<verbatim passage>\" (decision-doc Assumptions & Risks)"
```

✅ Verified: When scoping-runner updates `sections[§N]`, aggregate from the subsection results using these rules:

| Subsection outcome set under `§N` | Write `sections[§N]` |
|---|---|
| Any subsection is `X` | `X` |
| Any subsection is `!` | `!` |
| All subsections are `N/A-s` | `N/A-s` |
| All subsections are `N/A-s` or `N/A-c`, and at least one is `N/A-c` | `N/A-c` |
| All subsections are `V` | `V` |
| Mixed applicable and non-applicable subsections (for example, some `V`, some `N/A-*`) | `X` |

✅ Verified aggregation notes:

- If a top-level section has both required and conditional subsections, any still-applicable subsection keeps the parent top-level key at `X` until dialogue resolves it.
- Required subsections should be treated as applicable inputs to this aggregation model, not as candidates for N/A assignment.
- During Scoping, applicable conditional subsections also remain unresolved inputs (`X`); this sub-skill does not produce `V`.
- Parent-skill iteration remains top-level first; once inside a top-level section, downstream dialogue proceeds subsection by subsection.

## Return Summary

✅ Verified: After all writes succeed, return exactly this structure with the actual derived ids:

```text
Scoping complete.
  N/A-s (structural): <space-separated subsection ids>
  N/A-c (content): <space-separated subsection ids>
  Remaining (X): <space-separated unresolved section ids>
  Next step: InDialogue
```
