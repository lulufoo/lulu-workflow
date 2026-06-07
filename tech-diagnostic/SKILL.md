---
name: tech-diagnostic
---

# tech-diagnostic

Domain holder for tech-level diagnostic decisions. Delegates the full DDF execution to the `diagnostic` kernel under tech domain constraints.

---

<HARD-GATE>
Do NOT proceed until you have read `../_runtime.md` and loaded:

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

### Role

You are acting as a **technical decision maker**. Frame all questions and analyses from the perspective
of system design, implementation constraints, and engineering trade-offs. Use technical vocabulary
(architecture, dependencies, interfaces, rollback) rather than product vocabulary.

### X Gate

Execute **all five** dimensions (in order):

1. Acceptance Criteria
2. Impact Surface
3. External Dependencies
4. Implementation Sketch
5. Gap Check

No dimensions are skipped.

### Decision-Doc

Write **all sections** as defined in the kernel template. No sections are omitted.

### Context Loading

Before the Open Channel (before Q), check whether a Delivered product-doc exists for this feature:

```
$CACHE_DIR/<cycle_id>/product/plan/   (look for the latest revision with Delivered state)
```

If a Delivered product-doc is found, load it as read-only context and tell the user:
"I've loaded the product-doc as context for this tech diagnostic."

If not found, proceed without it.

### After DC

Tell user: "Tech diagnostic is complete. The next step is `/tech-plan` (alias: `tp`)."

## start

Execute the `start` command from `diagnostic/SKILL.md`, passing `tech-diagnostic` as the stage:

- Stage: `tech-diagnostic`
- Cache subdir: `tech/diagnostic`
- Apply all constraints from `## Domain Constraints` above throughout the session.
> If start.py exits non-zero ("Gate blocked: <stage> is not Delivered"): tell the user which prior stage must be delivered first. Do not retry start.
