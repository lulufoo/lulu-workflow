---
name: fact-disposition-runner
description: >-
  Compose fact-intake L1: disposition classify on cut facts.
---

# fact-disposition-runner

Classify existing `_facts.json` atoms into `carried` / `quarantined` /
`not_needed`; write disposition + lens_tags (Intent rule).

**Must:** `$FACT_DISPOSITION_BUILD context`; write dispositions; pass
tightened validate.  
**Must not:** Cut; Confirm human gate; edit source doc; write `discovered`.

## Input

```text
REVISION_DIR: <abs revision root>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
SOURCE_PATH: <abs intake SoT>
```

## Cognition

Context terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| fact atom, `lens_tags` | `../../references/cognition/fact.md` |
| registry `intent`, `intent_boundary` | `../../references/cognition/lens.md` |
| `derivation.disposition`, `rule_id` | `../../references/cognition/producer/provenance.md` |
| role `consume_policy` | `../../references/cognition/profile/role.md` |

One verdict per atom:

```text
not_needed  ⇐ one consume_policy rule holds        (cite rule_id; no tags)
carried     ⇐ some lens intent owns it             (tags = those lenses)
quarantined ⇐ otherwise                            (no tags)
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACT_DISPOSITION_BUILD` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-disposition-runner/scripts/fact_disposition_build_control.py"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/facts/facts_control.py"` |

Build: `--help` · `context`.  
Facts: `--help` · `write` · `validate`.

## Execution

1. Bind Input.  
2. `$FACT_DISPOSITION_BUILD context …` (section-registry + role consume_policy).  
3. don't-list → `not_needed`; Intent → `carried`/`quarantined`; repair don't-list false kills.  
4. Persist via `$FACTS_CTL write`.  
5. `$FACTS_CTL validate … --require-derivation`.

**Done:** validate exit 0.

## Summary

```text
Fact-disposition complete.
  Facts: <path>
  Disposition counts: carried=<n> quarantined=<n> not_needed=<n>
  Status: ok
```
