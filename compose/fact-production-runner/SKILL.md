---
name: fact-production-runner
description: >-
  Compose fact-production tool skill. Whole-batch conclusion→facts and
  open→facts settlement with human confirm. Declared by inductive G2/G3;
  not wired to deductive this wave.
---

# fact-production-runner

Use when a compose caller **declares** this skill for writing `_facts.json`
(conclusion batch or open settlement). Does not own Topic Loop dialogue.

**Must:** write facts only via `$FACT_PRODUCTION_CTL` after human `--confirm`.  
**Must not:** silently write; use Formal arc paths; invent product semantics.

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACT_PRODUCTION_CTL` | `python3 "$SKILL_ROOT/compose/fact-production-runner/scripts/fact_production_control.py"` |

Subcommands: `--help` · `commit` · `cancel` · `settle-open` · `update`.

## DONE / failure

- **DONE (commit / settle-open / update):** exit 0; stdout JSON includes `stale_signal` / `suggest_check` when written.
- **DONE (cancel):** exit 0; `written: false`; `_facts.json` unchanged.
- **Failure:** non-zero; message on stderr (missing `--confirm`, bad payload, open not open).
