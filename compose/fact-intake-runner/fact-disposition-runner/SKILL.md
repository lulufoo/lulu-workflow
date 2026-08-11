---
name: fact-disposition-runner
description: >-
  Compose fact-intake L1: disposition classify after intake eval done.
---

# fact-disposition-runner

Classify existing `_facts.json` atoms (post Intake Eval) into
`carried` / `quarantined` / `not_needed`; write disposition + lens_tags
(Intent rule).

**Must:** require `eval_status=done`; `$FACT_DISPOSITION_BUILD_CTL context`; write
dispositions; pass tightened validate.  
**Must not:** Cut; Eval; Confirm human gate; edit source doc; write `discovered`.

## Input

```text
REVISION_DIR: <revision or focus-L dir>
PROJECT_ROOT: <abs project root>
COMPOSE_PROFILE: <profile id>
CYCLE_ID: <cycle id>
SOURCE_PATH: <abs intake SoT>
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACT_DISPOSITION_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-disposition-runner/scripts/fact_disposition_build_control.py"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

Build: `--help` · `context`.  
Facts: `--help` · `write` · `validate`.

## Execution

1. Bind Input; refuse unless intake-eval gate is `eval_status=done`.  
2. `$FACT_DISPOSITION_BUILD_CTL context …` (section-registry + role consume_policy).  
3. don't-list → `not_needed`; Intent → `carried`/`quarantined`; repair don't-list false kills.  
4. Persist via `$FACTS_CTL write`.  
5. `$FACTS_CTL validate … --require-derivation --require-consume-policy`.

**Done:** validate exit 0.

## Summary

```text
Fact-disposition complete.
  Facts: <path>
  Disposition counts: carried=<n> quarantined=<n> not_needed=<n>
  Status: ok
```
