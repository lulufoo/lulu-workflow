---
name: chapter-write-runner
description: >-
  Compose chapter-write and assemble runner for narrative-arc write units.
---

# chapter-write-runner

Write each narrative-arc chapter from its claim ticket, then assemble the
compose document.

## Input

```text
REVISION_DIR: <revision or inductive out dir>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
OUTPUT_DOC_PATH: <abs path to compose output doc>
ARC_PATH: _narrative-arc.json
```

## Cognition

Ticket terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| ticket facts, `fact_ids`, anchors | `../references/cognition/fact.md` |
| ticket `lens`, `lens_intent` | `../references/cognition/lens.md` |
| chapter, `cid`, body | `../references/cognition/chapter.md` |
| ticket `writing_cognition` | `references/writing-cognition.md` |

One chapter composes them:

```text
body(chapter) = Write( facts_ℓ ; writing_cognition_ℓ )
  content ⊆ facts_ℓ        anchors(facts_ℓ) ⊆ tokens(body)
```

## Load rule

1. Load `references/write-protocol.md`.  
2. Load `contracts/delivery.md` and complete the pipeline.

## Script Macros

| Macro | Command |
|-------|---------|
| `$CHAPTER_WRITE_BUILD` | `python3 "$SKILL_ROOT/compose/chapter-write-runner/scripts/chapter_write_build_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/writing/chapter_write_state_control.py"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/writing/compose_doc_control.py"` |

Build: `--help` · `context`.  
Write-state: `--help` · `sync` · `status` · `begin` · `complete`.  
Doc: `--help` · `init-doc` · `assemble-arc`.

## Summary

Return exactly the Summary shape in `contracts/delivery.md`.
