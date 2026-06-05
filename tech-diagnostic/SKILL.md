---
name: tech-diagnostic
---

# tech-diagnostic

Domain holder for tech-level diagnostic decisions. Delegates the full DDF execution to the `diagnostic` kernel under tech domain constraints.

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

`$SKILL_DIR` = `$SKILL_ROOT/tech-diagnostic`

---

## Domain Constraints

These constraints are injected into the `diagnostic` kernel. The kernel's `Domain Constraints HARD-GATE` will detect and apply them.

### X Gate

Execute **all five** dimensions (in order):

1. Acceptance Criteria
2. Impact Surface
3. External Dependencies
4. Implementation Cost
5. Expected Outcome

No dimensions are skipped.

### Decision-Doc

Write **all sections** as defined in the kernel template. No sections are omitted.

### Context Loading

Before the Open Channel (before Q), check whether a Delivered product-doc exists for this feature:

```
$CACHE_DIR/<feature_id>/product/plan/   (look for the latest revision with Delivered state)
```

If a Delivered product-doc is found, load it as read-only context and tell the user:
"I've loaded the product-doc as context for this tech diagnostic."

If not found, proceed without it.

### After DC

Tell user: "Tech diagnostic is complete. The next step is `/tech-plan` (alias: `tp`)."

---

## Stage Entry (Gate Check)

Before starting this stage, the AI must:

1. Read `features.json` (or `topics.json`) to confirm the current container type (`topic` / `feature`) and container ID.
2. Call `check_gate(container_id, to_stage="tech-diagnostic", cycle_type, cache_dir)` via the `hook_guard.py` script:
   - If `ok == False`: stop, output `reason` to user, do not proceed.
   - If `ok == True`: continue.
3. If container is `feature` and has `topic_id`: call `get_topic_doc(container_id, "tech-diagnostic", cache_dir)` to retrieve the topic reference document.
   - If path returned: inform user of the topic doc path and load it as context.
   - If `None`: skip silently.
   - If `ValueError`: stop, output error to user, do not proceed.
4. Inform user of the current cycle layer:
   - `topic` container → shaping cycle (architecture exploration)
   - `feature` container → spec cycle (implementation spec)

---

## start

Execute the `start` command from `diagnostic/SKILL.md`, passing `tech-diagnostic` as the stage:

- Stage: `tech-diagnostic`
- Cache subdir: `tech/diagnostic`
- Apply all constraints from `## Domain Constraints` above throughout the session.
