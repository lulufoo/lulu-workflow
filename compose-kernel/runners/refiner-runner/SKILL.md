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

`read-gap-item` → `$GAP.refiner` includes `gap_kind`, `repair_class`, `fix_mode`, `degraded_from`, and KW / Upstream / Intent fields.

| gap_kind | Target source |
|----------|---------------|
| `kw` | `kw_criteria.kw{target_kw}` |
| `upstream_violation` / `upstream_coverage` | `upstream_criteria.expected` |
| `intent_coverage` / `intent_violation` | `intent_criteria.expected` + `## {section_key}` kw block + scope doc excerpts cited in `intent_criteria.decision_intent` |
| `structural` | `intent_gap` (describes specific defect) + `fixer_action` from structural-probe-criteria |

**Anchor:** `intent_gap`. **Target:** table above.

`$ROUND_CONTROL`: `{SKILL_ROOT}/compose-kernel/SKILL.md` → Script Macros. Use `$ROUND_CONTROL read-section-body --section {section_key}` to load section bodies (not H2 title grep).

For intent gaps, read scope doc from `$CTX.scope_doc_path` and locate the paragraph(s) behind `intent_criteria.decision_intent`.

For display-title updates: `$FETCH_COMPOSE section-registry` → `sections.{section_key}.heading` as type anchor (same rules as initializing-runner I2e).

## Step 0.5 — repair_class routing

Route by `$GAP.refiner.repair_class` **before** drafting:

### mechanical (fix_mode: auto)

Applies to `gap_kind: structural` and `gap_kind: kw0_pending`.

1. Run:
   ```
   python3 mechanical_fixer.py apply-mechanical-fix \
       --doc-path {COMPOSE_DOC_PATH} \
       --gap-item '<$GAP.refiner JSON>'
   ```
2. **Exit 0** → fix applied. Set `handled_by: script`. Call `update-gap-status --status resolved`. Show user:
   ```
   ✔ Auto-fixed [{GAP_ITEM_ID}] ({gap_kind}): {result.message}
   ```
   **Stop. Do not enter Step 3.**
3. **Exit 2 (DEGRADE)** → script cannot handle this item. Update in-memory item:
   - `repair_class → kw_subsection`, `fix_mode → auto`, `degraded_from → mechanical`, `handled_by → null`
   - Call `update-gap-status` to keep `open`. Show user:
     ```
     ⚠ Degraded [{GAP_ITEM_ID}]: mechanical fix unavailable — routing to LLM (kw_subsection).
     ```
   - Fall through to **kw_subsection** path below.
4. **Exit 1 (hard error)** → emit error, abort refinement for this item.

### kw_subsection (fix_mode: auto or confirm)

Applies to `gap_kind: kw` and degraded items.

- If `fix_mode: auto`: draft + apply without blocking prompt. Set `handled_by: llm`.
- If `fix_mode: confirm` (profile override): present draft to user for approval before Step 5 write.

Proceed to **Step 3 (KW draft path)**.

### semantic_review (fix_mode: confirm)

Applies to `gap_kind: upstream_*` and `intent_*`.

**Always requires human confirmation before write.** Proceed to **Step 3** (Upstream or Decision intent draft path) and present draft before Step 5.

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
   - Keep or update `### {display_title} <!-- section-key:{section_key} -->` on the anchor line.
   - **Never remove or alter** `<!-- section-key:… -->`.
2. `write-refiner-artifact --json …`
3. `update-gap-status --status resolved`

After write, orchestrator re-probes: KW + upstream + decision intent.

## Step 6 — Handling summary

After Step 5 write (or auto-fix in Step 0.5), emit a one-line handling summary using `handled_by` and `degraded_from`:

| handled_by | degraded_from | Summary line |
|------------|---------------|--------------|
| `script` | — | `✔ script [{GAP_ITEM_ID}] {gap_kind} — {result.message}` |
| `llm` | — | `✔ llm [{GAP_ITEM_ID}] {gap_kind} — auto-filled` |
| `llm` | `mechanical` | `✔ llm [{GAP_ITEM_ID}] {gap_kind} — degraded from mechanical; LLM-filled` |
| `llm+human` | — | `✔ llm+human [{GAP_ITEM_ID}] {gap_kind} — confirmed by user` |

Set `handled_by` on the gap item via `update-gap-status` extended payload before writing the refiner artifact.

## Return

```text
Refiner complete — {GAP_ITEM_ID} ({gap_kind}) | repair_class: {repair_class} | handled_by: {handled_by}.
  Next: orchestrator re-probes active section
```
