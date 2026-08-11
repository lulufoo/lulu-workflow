---
name: chapter-write-runner
description: >-
  Compose chapter-write and assemble runner for narrative-arc write units.
---

# chapter-write-runner

For each arc write unit, write a readable chapter body from that chapter's
begin-ticket facts only—no invention beyond the ticket, preserve anchors, mark
gaps with 待决—then assemble a document whose visible titles come from the
narrative arc.

## Boundaries

**Must:** bind Input; load protocol then delivery; obtain session context via
`$CHAPTER_WRITE_BUILD_CTL context`; drive Write via `$CHAPTER_WRITE_STATE`
claim-current; `init-doc` then `assemble-arc` with the same preamble.  
**Must not:** paste facts in the caller prompt; Read `_facts.json` for Write
substance; fetch full `section-form-registry` / `section-registry` during Write;
accept `$CODE_GROUNDING` or `$SCOPE_REF_PATH` as Input.

## Input

```text
REVISION_DIR: <revision or inductive out dir>
PROJECT_ROOT: <abs project root>
COMPOSE_PROFILE: <profile id>
CYCLE_ID: <cycle id>
OUTPUT_DOC_PATH: <abs path to compose output doc>
ARC_PATH: <arc file relative to slice or absolute; required>
```

**Must not (Input):** facts body · facts file path · `$CODE_GROUNDING` ·
`$SCOPE_REF_PATH`.

`ARC_PATH` is required each call. Init typically passes `_narrative-arc.json`
(default sync/assemble basename). Do not omit the field.

## Load rule

1. Bind Input.  
2. Load `references/write-protocol.md`.  
3. Load `contracts/delivery.md` and complete the pipeline.

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
