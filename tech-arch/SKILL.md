---
name: tech-arch
description: >-
  Topic-cycle technical architecture shaping stage. Use when cycle_type is topic and
  tech-diagnostic is Delivered.
disable-model-invocation: true
---

# tech-arch

Topic shaping terminal stage: technical architecture document after tech-diagnostic.

**Scope:** Topic cycles only. Feature technical planning uses `tech-plan` / `tech-design`.

## Start

```bash
python3 "$SKILL_ROOT/tech-arch/scripts/ta_start.py" \
  --project-root "$(pwd)" --cycle-id "$CYCLE_ID"
```
