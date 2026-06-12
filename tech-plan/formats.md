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

Schema v3. Full field list:

```bash
python3 {$SKILL_ROOT}/eval/scripts/evaluate_state_schema.py --schema
```

Key fields: `eval_status` (`active` | `done` | `abandoned`), `fix_phase` (`probe` | `artifact-remediation` | `sot-remediation` | `done`), `dimension_status` (JSON map: dim_id → `pending` | `in_progress` | `probed` | `complete`), `issue_counts` (JSON map per dimension).

---

## evaluate{M}/tech-review-e{M}N.md

SSOT: header from `{$SKILL_ROOT}/eval/review.template.md`; validate via
`python3 {$SKILL_ROOT}/eval/scripts/review_schema.py --schema`. Cell content: `{$SKILL_ROOT}/eval/SKILL.md`.
