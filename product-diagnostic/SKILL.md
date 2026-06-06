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

## start

Execute the `start` command from `diagnostic/SKILL.md`, passing `product-diagnostic` as the stage:

- Stage: `product-diagnostic`
- Cache subdir: `product/diagnostic`
- Apply all constraints from `## Domain Constraints` above throughout the session.
> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.
