---
name: lulu-blueprint
description: >-
  Topic-cycle product architecture shaping stage. Use when cycle_type is topic and
  lulu-bet is Delivered.
disable-model-invocation: true
---

# lulu-blueprint

Topic shaping stage: product architecture document after lulu-bet.

**Scope:** Topic cycles only. Feature PRD cycles use `lulu-spec`.

## Start

```bash
python3 "$SKILL_ROOT/lulu-blueprint/scripts/pa_start.py" \
  --project-root "$(pwd)" --cycle-id "$CYCLE_ID"
```
