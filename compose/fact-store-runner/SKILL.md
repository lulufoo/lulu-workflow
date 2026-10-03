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
| `$FACT_STORE_CTL` | `python3 "$SKILL_ROOT/compose/fact-store-runner/scripts/fact_production_control.py" --project-root "$PROJECT_ROOT"` |

Subcommands: `--help` · `propose` · `ack` · `consume` · `revoke` · `reconcile` · `recover`.

## Group settle

`propose --kind settle_open --open-ids O-1,O-3 --facts-json …` lands several
Opens of one lens in one active batch under one permit and one ACK. Every
fact names its `open_id`, and every listed Open needs at least one fact.
Single `--open-id` is unchanged.

## DONE / failure

- **DONE (consume):** exit 0; stdout JSON includes `facts_total` and the written fact ids.
- **DONE (revoke):** exit 0; no facts written.
- **Failure:** non-zero; message on stderr (unacknowledged/stale permit, digest mismatch, bad payload, open not open).
