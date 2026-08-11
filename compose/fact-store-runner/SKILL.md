---
name: fact-store-runner
description: >-
  Compose fact store tool skill. Permit-gated fact mutations for G2/G3:
  propose an exact preview, obtain human ACK, then consume it. Declared by G2/G3;
  Inductive store channel (propose/ack/consume); not wired to deductive this wave.
---

# fact-store-runner

Use when a compose caller **declares** this skill for writing `_facts.json`
(conclusion batch or open settlement). Does not own Topic Loop dialogue.

**Must:** `propose` → display the exact preview → obtain user ACK → `ack` → `consume`.  
**Must not:** silently write; use Formal arc paths; invent product semantics.

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACT_STORE_CTL` | `python3 "$SKILL_ROOT/compose/fact-store-runner/scripts/fact_production_control.py"` |

Subcommands: `--help` · `propose` · `ack` · `consume` · `revoke` · `reconcile` · `recover`.

## DONE / failure

- **DONE (consume):** exit 0; stdout JSON includes `stale_signal` / `suggest_check` when written.
- **DONE (revoke):** exit 0; no facts written.
- **Failure:** non-zero; message on stderr (unacknowledged/stale permit, digest mismatch, bad payload, open not open).
