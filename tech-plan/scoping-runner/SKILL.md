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
| `$META_PATH` | Raw markdown source for the tech-plan meta rules (`tpt_meta_url`) |
| `$DECISION_DOC_PATH` | Absolute path to the current cycle `decision-doc.md` |
| `$TECH_DOC_PATH` | Absolute path to `revision{N}/tech-doc.md` |
| `$SECTION_PROGRESS_PATH` | Absolute path to `revision{N}/section-progress.md` |
| `$DRAFTING_PROGRESS_PATH` | Absolute path to `revision{N}/drafting-progress.md` |

✅ Verified: This sub-skill does not fetch conditional rules from a runtime path. The authoritative inputs needed from the meta/state files are embedded below and must be treated as the execution source of truth.

## Embedded Authoritative References

✅ Verified: Use these embedded references exactly as the read model. Do not load separate local meta/state files at runtime for these rules.

### Embedded Section Conditions

✅ Verified source: `.cache/20-tech-plan-spec-meta.md` → `## Section Conditions`

```markdown
> Required sections (always included): §1.1, §1.2, §2, §3, §4.1-4.4, §5, §6, §8.1-§8.2, §9.1, §9.2, §10
>
> Conditional sections - scoping-runner evaluates each trigger and marks non-applicable sections `N/A-s` or `N/A-c`.
> `Trigger Type`: `structural` = keyword match on `**Intent:**` line; `content` = read the specified decision-doc section body.
> `Evidence Source`: exact decision-doc field scoping-runner must locate to find denying evidence.
>
> | Section | Trigger | Trigger Type | Evidence Source |
> |---|---|---|---|
> | §1.3 Current State Analysis | contains keyword "bugfix" or "refactor" in `**Intent:**` | structural | `**Intent:**` line |
> | §4.5 Interface Contract | change introduces or modifies interfaces | content | `### Impact Surface` (Change Type column) + `### Implementation Sketch > Key changes` |
> | §4.6 Detailed Design | module-level elaboration needed beyond §4.1 sketch | content | `### Implementation Sketch > Key changes` |
> | §7.1 Observable | change has a runtime observability surface | content | `### Impact Surface` (Layer column: runtime / infra) |
> | §7.2 Gradual Rollout | change can be released to subset of users/traffic | content | `## Scope > Applies to` + `### Implementation Sketch` |
> | §7.3 Operable | change requires post-deployment operational management | content | `### Impact Surface` + `### Implementation Sketch > Critical constraints` |
> | §8.3 Pre-Implementation Checklist | §2.5 has open assumptions or S0 prerequisite items | content | `## Assumptions & Risks` (rows with `[待验证]` status) |
> | §9.3 Data Repair | change involves data migration or orphaned records | content | `### Implementation Sketch > Key changes` |
> | §9.4 Open Questions | unresolved questions requiring human decision | content | `## Assumptions & Risks` (rows flagged H-risk `[待验证]`) |
```

### Embedded Section Status Symbols

✅ Verified source: `.cache/drafting-state-machine.json` → `section_symbols`

```json
{
  "X": "Pending - skeleton placeholder; InDialogue X-mode (build from scratch)",
  "I": "Initialized - seeded from decision-doc or retained on Reopen; InDialogue I-mode (display & confirm)",
  "N/A-s": "Not Applicable (structural) - excluded by change type",
  "N/A-c": "Not Applicable (content) - condition not triggered per decision-doc",
  "D": "In Dialogue - section currently being processed (only one D at a time)",
  "V": "Confirmed - user explicitly confirmed; content locked",
  "!": "Expired - upstream Reopen invalidated; requires re-review",
  "S": "Skipped - user explicitly confirmed exclusion (N/A-s / N/A-c -> S)"
}
```

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

1. Load the embedded `Section Conditions` table and extract all conditional sections.
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
