---
name: fact-store-runner
description: >-
  Compose fact store: permit-gated write of the slice fact set.
---

# fact-store-runner

Atomize the declared business object and write `_facts.json`. Done when
`$FACT_STORE_CTL consume` exits 0.

**Must:** cut from the declared object → `propose` → `consume`.  
**Must not:** show a store preview; obtain human ACK; invent product semantics;
use Formal arc paths.

## Input

```text
append:      confirmed conclusion + topic scope
settle_open: Land open ids + Process results
```

`kind` constrains write fields only. One cut standard.

## Cognition

Output terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| fact atom, `anchors`, `lens` | `../references/cognition/fact.md` |
| `origin`, `derivation` | `../references/cognition/producer/provenance.md` |
| registry lens | `../references/cognition/lens.md` |
| role | `../references/cognition/profile/role.md` |

## Script Macros

Contract in `--help`.

| Macro | Command |
|---|---|
| `$FACT_STORE_CTL` | `python3 "$SKILL_ROOT/compose/fact-store-runner/scripts/fact_production_control.py" --project-root "$PROJECT_ROOT"` |

## Group settle

One permit lands several Opens of one lens in the active batch. Every fact
names its `open_id`; every listed Open needs at least one fact.

## Boundaries

- Controls: `propose` once, then `consume` once. A failed call fails the pass.
- `--facts-json` is the mechanical payload after cutting.
- Evidence closure: this SKILL, the Cognition units, and the declared object.
- Do not list scripts or read another cycle.

## Execution

1. Bind Input.  
2. Cut atoms from the declared object.  
3. `$FACT_STORE_CTL propose`  
4. `$FACT_STORE_CTL consume`

**Done:** consume exit 0.

## DONE / failure

- **DONE (consume):** exit 0; stdout JSON includes `facts_total` and the written fact ids.
- **DONE (revoke):** exit 0; no facts written.
- **Failure:** non-zero; message on stderr.
