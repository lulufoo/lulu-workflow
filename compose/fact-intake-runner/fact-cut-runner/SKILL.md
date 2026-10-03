---
name: fact-cut-runner
description: >-
  Compose fact-intake L1: whole-doc cut and disposition classify.
---

# fact-cut-runner

Read `$SOURCE_PATH` once and write classified seed atoms. Done when
`$FACTS_CTL validate --require-derivation` exits 0.

**Must:** `$FACT_CUT_BUILD context`; cut+tag+write.  
**Must not:** Confirm; Eval; `fact-store-runner`; edit source doc; write
`discovered`.

## Input

```text
REVISION_DIR: <abs revision root>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
SOURCE_PATH: <abs intake SoT>
REQUIRE_SEED_ORIGIN: <true|false; default false>
```

## Cognition

Output terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| fact atom, `anchors`, `lens` | `../../references/cognition/fact.md` |
| `origin.type=seed`, `derivation.upstream_ref`, `disposition`, `rule_id` | `../../references/cognition/producer/provenance.md` |
| registry `intent`, `intent_boundary` | `../../references/cognition/lens.md` |
| role `consume_policy` | `../../references/cognition/profile/role.md` |

One verdict per atom, assigned while cutting:

```text
not_needed  ⇐ one consume_policy rule holds        (cite rule_id; omit lens)
carried     ⇐ some lens intent owns it             (lens = one key, chosen per lens.md)
quarantined ⇐ otherwise                            (omit lens)
```

One lens per fact: read its source section (`derivation.upstream_ref`) first;
if still ambiguous, take the lens whose intent is closest. Splitting is not
decided here. After the last atom, repair don't-list false kills.

## Script Macros

Contract in `--help`.

| Macro | Command |
|---|---|
| `$FACT_CUT_BUILD` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-cut-runner/scripts/fact_cut_build_control.py"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/facts/facts_control.py"` |

## Boundaries

- Control calls: `context` once; `write` once; `validate --require-derivation` once. Add `--require-seed-origin` when `$REQUIRE_SEED_ORIGIN=true`. A failed call fails the pass.
- Evidence closure: `context` stdout, this SKILL, the Cognition units, and `$SOURCE_PATH`. Read nothing outside the closure.
- Do not list scripts or read another cycle's facts.
- Write seed + `upstream_ref` + disposition.

## Execution

1. Bind Input.  
2. `$FACT_CUT_BUILD context --revision-dir … --project-root … --cycle-id …`  
3. Whole-doc cut; tag each atom; repair don't-list false kills.  
4. `$FACTS_CTL write`.  
5. `$FACTS_CTL validate --require-derivation`.

**Done:** validate exit 0.

## Summary

```text
Fact-cut complete.
  Facts: <path>
  Facts count: <N>
  Disposition counts: carried=<n> quarantined=<n> not_needed=<n>
  Status: ok
```
