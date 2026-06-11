---
rule-guard:
  globs:
    - "**/*.md"
---

# Session File Formats

Reference document for `tech-plan/SKILL.md`. Read on demand when writing any session file.

---

## revision{N}/workflow-state.md

```markdown
---
version: 1
workflow: tech-doc
mode: product
current_state: Drafting
evaluate_round: 0
skip_evaluate_requested: false
product_ref: /abs/path/$CACHE_DIR/<cycle_id>/product/plan/revision1/product-doc.md
carry_forward_ref: ""
updated_at: 2026-05-17T09:00:00+08:00
---
```

> `mode`: set by `start.py`; preserve on every manual write of `workflow-state.md`.
> `skip_evaluate_requested: true`: only for `Drafting → ReadyForDelivery`; omit when writing `Delivered`.

---

## revision{N}/evaluate-state.md

```markdown
---
version: 1
phase: evaluate
current_dimension: e1

e1_status: pending
e1_total_issues: 0
e1_resolved_issues: 0

e2_status: pending
e2_total_issues: 0
e2_resolved_issues: 0

total_issues: 0
resolved_issues: 0

fix_severity: ""
fix_severity_reason: ""
---
```

---

## evaluate{M}/tech-review-e{M}N.md

Each review file shares the same structure; column set varies by dimension:

```markdown
# {E1|E2} Review: {Intent Alignment|Codebase Consistency} — revision{N} round {M}

**Date:** YYYY-MM-DD
**Refs:** [E1: product_ref + ptc_url / E2: relevant code paths]

| # | Issue | [E2: file] | Severity | Status | Decision |
|---|-------|-----------|----------|--------|---------|
| {E1|E2}-1 | ... | ... | critical/medium/minor | ✅ Fixed | fix |
```
