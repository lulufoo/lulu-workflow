---
name: product-diagnostic
---

# product-diagnostic

Domain holder for product-level diagnostic decisions. Delegates the full DDF execution to the `diagnostic` kernel under product domain constraints.

---

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

<HARD-GATE>
Do NOT proceed until you have read `../diagnostic/SKILL.md` in full.
All DDF rules, gates, and registers defined there apply to this session.
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/product-diagnostic`

---

## Domain Constraints

These constraints are injected into the `diagnostic` kernel. The kernel's `Domain Constraints HARD-GATE` will detect and apply them.

### X Gate

Execute **only** the following dimensions (in order):

1. Acceptance Criteria
2. Impact Surface
3. Expected Outcome

Do **NOT** execute: External Dependencies, Implementation Cost.

### Decision-Doc

Omit the following sections from the written decision-doc:

- External Dependencies
- Implementation Cost

All other sections are required as defined in the kernel template.

### After DC

Tell user: "Product diagnostic is complete. The next step is `/product-plan` (alias: `pp`)."

---

## Stage Entry (Gate Check)

Before starting this stage, the AI must:

1. Read `features.json` (or `topics.json`) to confirm the current container type (`topic` / `feature`) and container ID.
2. Call `check_gate(container_id, to_stage="product-diagnostic", cycle_type, cache_dir)` via the `hook_guard.py` script:
   - If `ok == False`: stop, output `reason` to user, do not proceed.
   - If `ok == True`: continue.
3. If container is `feature` and has `topic_id`: call `get_topic_doc(container_id, "product-diagnostic", cache_dir)` to retrieve the topic reference document.
   - If path returned: inform user of the topic doc path and load it as context.
   - If `None`: skip silently.
   - If `ValueError`: stop, output error to user, do not proceed.
4. Inform user of the current cycle layer:
   - `topic` container → shaping cycle (architecture exploration)
   - `feature` container → spec cycle (implementation spec)

---

## start

Execute the `start` command from `diagnostic/SKILL.md`, passing `product-diagnostic` as the stage:

- Stage: `product-diagnostic`
- Cache subdir: `product/diagnostic`
- Apply all constraints from `## Domain Constraints` above throughout the session.
