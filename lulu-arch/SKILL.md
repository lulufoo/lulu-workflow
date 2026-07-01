---
name: lulu-arch
description: >-
  Topic-cycle technical architecture shaping stage. Use when cycle_type is topic and
  lulu-approach is Delivered.
disable-model-invocation: true
---

# lulu-arch

Topic shaping terminal stage: technical architecture document after lulu-approach.

**Scope:** Topic cycles only. Feature technical planning uses `lulu-plan` / `lulu-design`.

## Start

```bash
python3 "$SKILL_ROOT/lulu-arch/scripts/ta_start.py" \
  --project-root "$(pwd)" --cycle-id "$CYCLE_ID"
```
