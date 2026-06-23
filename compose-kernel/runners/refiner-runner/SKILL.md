---
name: refiner-runner
description: >-
  Round Iteration refiner for compose-profile drafting. Refines KW sub-section
  gaps, section-level Upstream gaps, or decision-intent gaps; multi-turn
  confirm; writes compose document + artifact.
---

# refiner-runner

Terminal runner. **One refinement** per invocation.

**Profile:** Pass the **same** `--profile` as parent `$ROUND_CONTROL` on `$FETCH_COMPOSE` when loading section-kw-criteria or section-registry.

## Inputs

```
CYCLE_DIR, CYCLE_ID, CYCLE_TYPE, ROUND_N, ROUND_DIR
GAP_ITEM_ID, COMPOSE_DOC_PATH
```

`read-gap-item` → `$GAP.refiner` includes `gap_kind`, `scope`, and KW / Upstream / Intent fields.

`read-context` → `$CTX.scope_doc_path` for intent gaps; `$CTX.compose_doc_path` for the active document path.

## Step 0 — Load gap item

| gap_kind | Target source |
|----------|---------------|
| `kw` | `kw_criteria.kw{target_kw}` |
| `upstream_violation` / `upstream_coverage` | `upstream_criteria.expected` |
| `intent_coverage` / `intent_violation` | `intent_criteria.expected` + `## {section_key}` kw block + scope doc excerpts cited in `intent_criteria.decision_intent` |

**Anchor:** `intent_gap`. **Target:** table above.

`$ROUND_CONTROL`: `{SKILL_ROOT}/compose-kernel/SKILL.md` → Script Macros. Use `$ROUND_CONTROL read-section-body --section {section_key}` to load section bodies (not H2 title grep).

For intent gaps, read scope doc from `$CTX.scope_doc_path` and locate the paragraph(s) behind `intent_criteria.decision_intent`.

For display-title updates: `$FETCH_COMPOSE section-registry` → `sections.{section_key}.heading` as type anchor (same rules as initializing-runner I2e).

## Step 3 — Draft

### KW (`scope: subsection`)

Preserve sub-section content; satisfy Target criteria.

When editing an intent block (`<!-- section-key:… -->`), re-derive `display_title` from `sections.{key}.heading` + updated body (initializing-runner I2e rules).

### Upstream (`scope: section`)

Read full `ACTIVE_SECTION` body + upstream section via `read-section-body`.

- Propose **which sub-section(s)** to add/edit to resolve the section-level gap.
- Present draft sub-section content; user confirms before write.

### Decision intent (`scope: section`)

Read full active section body + decision-doc relevant passages + section kw block.

- Propose edits that resolve `intent_gap` without contradicting decision-doc.
- For Tasks + AC coverage gaps, add or clarify task rows that trace the cited AC.
- Present draft; user confirms before write.

## Step 5 — Write

1. Write confirmed content to `COMPOSE_DOC_PATH` within the section located by `<!-- section-key:{section_key} -->`.
   - **Feature docs:** keep or update `### {display_title} <!-- section-key:{section_key} -->` on the anchor line.
   - **Topic docs:** you may change the H2 display text before the anchor comment.
   - **Never remove or alter** `<!-- section-key:… -->`.
2. `write-refiner-artifact --json …`
3. `update-gap-status --status resolved`

After write, orchestrator re-probes: KW + upstream + decision intent.

## Return

```text
Refiner complete — {GAP_ITEM_ID} ({gap_kind}).
  Next: orchestrator re-probes active section
```
