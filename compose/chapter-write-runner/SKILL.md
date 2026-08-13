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

## Load rule

1. Load `references/write-protocol.md`.  
2. Load `contracts/delivery.md` and complete the pipeline.

## Script Macros

| Macro | Command |
|-------|---------|
| `$CHAPTER_WRITE_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/chapter-write-runner/scripts/chapter_write_build_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_write_state_control.py"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py"` |

Build: `--help` · `context`.  
Write-state: `--help` · `sync` · `status` · `begin` · `complete`.  
Doc: `--help` · `init-doc` · `assemble-arc`.

## Summary

Return exactly the Summary shape in `contracts/delivery.md`.
