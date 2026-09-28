---
name: narrative-arc-runner
description: >-
  Compose semantic narrative-arc builder for write-ready document spines.
---

# narrative-arc-runner

Produce the document's narrative spine: outline stations come from settled
facts' substance story and are ordered for Role-reviewable reading, so titles
and structure alone present a Domain-audience through-line—not a lens catalog
or fact list.

## Boundaries

**Must:** bind Input; follow `references/candidate-build.md` through Write.  
**Must not:** use topic / old arc / lens order as the spine; use lens clusters;
persist a candidate that failed or skipped Check; invent a second schema
or `formal|collab` target fork.

## Input

```text
REVISION_DIR: <revision or inductive out dir>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
OUTPUT_PATH: <arc file relative to slice or absolute>
```

Do **not** paste fact bodies — read via `context`.

## Cognition

Context terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| `context` facts, `fact_ids` | `../references/cognition/fact.md` |
| `lens_tags`, registry lens relations | `../references/cognition/lens.md` |
| arc, group, leaf, station, `mapped` / `write_ready` | `../references/cognition/writing/narrative-arc.md` |
| chapter, placement | `../references/cognition/writing/chapter.md` |
| Domain `cognitive_frame`, `expression_conventions.scannability`, `audience_type` | `../references/cognition/profile/domain.md` |
| Role `priority_tendency` | `../references/cognition/profile/role.md` |

Placement composes them:

```text
place(fact) = one leaf → one chapter,  chapter.lens ∈ fact.lens_tags
```

The arc gives topology and titles; `lens_tags` decide membership only.
Role orders the stations; Domain sets the through-line and split rule.
How binding each is lives in `references/candidate-build.md`.

## Run

One arc. Follow only the unit named in the current step.

1. Bind Input.
2. Read `../references/cognition/writing/narrative-arc.md`.
3. Follow `references/candidate-build.md` through Write.

## Summary

Return this shape only.

```text
status: done|failed
output_path: <OUTPUT_PATH>
wrote: true|false
write_ready: true|false
error: <empty or message>
```

1. `status=done` only when `wrote=true` and `write_ready=true`.
2. Otherwise `status=failed` and `wrote=false`.
