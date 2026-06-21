---
name: product-arch
description: >-
  Topic-cycle product architecture shaping stage. Use when cycle_type is topic and
  product-diagnostic is Delivered.
disable-model-invocation: true
---

# product-arch

Topic shaping stage: product architecture document after product-diagnostic.

**Scope:** Topic cycles only. Feature PRD cycles use `product-spec`.

## Start

```bash
python3 "$SKILL_ROOT/product-arch/scripts/pa_start.py" \
  --project-root "$(pwd)" --cycle-id "$CYCLE_ID"
```
