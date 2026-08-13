---
name: fact-cut-runner
description: >-
  Compose fact-intake L1: whole-doc cut to _facts.json with seed and
  upstream_ref; no disposition classify.
---

# fact-cut-runner

Read `$SOURCE_PATH` once; write focus-slice `_facts.json` atoms with non-empty
`derivation.upstream_ref` and `origin.type=seed`; **omit** disposition.

**Must:** `$FACT_CUT_BUILD_CTL context` then cut+write; pass structural validate.  
**Must not:** disposition; confirm; Eval; `fact-store-runner`; edit source doc; write
`discovered` or non-empty disposition.

## Input

```text
REVISION_DIR: <revision or focus-L dir>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
SOURCE_PATH: <abs intake SoT>
REQUIRE_SEED_ORIGIN: <true|false; default false>
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACT_CUT_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-cut-runner/scripts/fact_cut_build_control.py"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

Build: `--help` · `context`.  
Facts: `--help` · `write` · `validate`.

## Execution

1. Bind Input.  
2. `$FACT_CUT_BUILD_CTL context --revision-dir … --project-root … --cycle-id …`  
3. Whole-doc cut → `$FACTS_CTL write … --intake-structure` (omit
   `derivation.disposition`; set seed + `upstream_ref`; add
   `--require-seed-origin` when `$REQUIRE_SEED_ORIGIN=true`).  
4. `$FACTS_CTL validate … --intake-structure` (same `--require-seed-origin` rule).

**Done:** validate exit 0.

## Summary

```text
Fact-cut complete.
  Facts: <path>
  Facts count: <N>
  Status: ok
```
