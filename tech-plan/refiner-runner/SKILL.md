---
name: refiner-runner
description: >-
  Round Iteration refiner for tech-plan drafting. Refines KW sub-section gaps or
  section-level Upstream gaps; multi-turn confirm; writes tech-doc + artifact.
---

# refiner-runner

Terminal runner. **One refinement** per invocation.

## Inputs

```
CYCLE_DIR, CYCLE_ID, CYCLE_TYPE, ROUND_N, ROUND_DIR
GAP_ITEM_ID, TECH_DOC_PATH
```

`read-gap-item` → `$GAP.refiner` includes `gap_kind`, `scope`, and either KW or Upstream fields.

## Step 0 — Load gap item

| gap_kind | Target source |
|----------|---------------|
| `kw` | `kw_criteria.kw{target_kw}` |
| `upstream_violation` / `upstream_coverage` | `upstream_criteria.expected` |

**Anchor:** `intent_gap`. **Target:** table above.

Use `$ROUND_CONTROL read-section-body --section {section_key}` to load section bodies (not H2 title grep).

## Step 3 — Draft

### KW (`scope: subsection`)

Preserve sub-section content; satisfy Target criteria.

Optional: when section is still a registry placeholder title, propose a content-derived display title for the H2 line.

### Upstream (`scope: section`)

Read full `ACTIVE_SECTION` body + upstream section via `read-section-body`.

- Propose **which sub-section(s)** to add/edit to resolve the section-level gap.
- Present draft sub-section content; user confirms before write.

## Step 5 — Write

1. Write confirmed content to `TECH_DOC_PATH` within the section located by `<!-- section-key:{section_key} -->`.
   - You may change the H2 display text before the anchor comment.
   - **Never remove or alter** `<!-- section-key:… -->`.
2. `write-refiner-artifact --json …`
3. `update-gap-status --status resolved`

## Return

```text
Refiner complete — {GAP_ITEM_ID} ({gap_kind}).
  Next: orchestrator re-probes active section
```
