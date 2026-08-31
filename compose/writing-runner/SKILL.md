---
name: writing-runner
description: >-
  Compose Writing orchestrator.
---

# writing-runner

Turn producer-written facts into a validated compose draft document.

## Scope

Fact production belongs to Inductive|Deductive (`inductive-runner` or
`deductive-runner`).

- **Must:** validate producer-written `_facts.json`.
- **Must not:** invent beyond facts; decide open choices.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_REF_PATH` | Absolute path to compose scope SSOT (Return echo only) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md); fallback `{REVISION_DIR}/tech-doc.md` when omitted |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |
| `$CODE_GROUNDING` | Boolean from `enter-writing` stdout |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)`

## Script Macros

| Macro | Command |
|-------|---------|
| `$WRITING_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/writing/writing_compose_control.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/facts/facts_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |

`$FACTS_CTL` subcommands used here: `--help` · `validate` · `status`.

`$NARRATIVE_ARC_CTL` subcommands: `--help` · `validate` · `write` · `show` · `list-chapters`.

## Execution

### Step 1 — Load

1. Bind Parent Inputs (`$REVISION_DIR`, `$OUTPUT_DOC_PATH`, `$CYCLE_ID`, `$SCOPE_REF_PATH` path hold, `$CODE_GROUNDING`).
2. Resolve `$PROJECT_ROOT` = `$(pwd)`.

**Done:** Parent required Inputs bound; `$PROJECT_ROOT` resolved; `$CODE_GROUNDING` boolean set. Proceed to Step 2.

### Step 2 — Validate facts

Producer already wrote `_facts.json`. Only validate:

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --project-root "$(pwd)"
```

Missing / invalid `_facts.json` → Blocking (return to producer; never re-atomize from scope).

Topology change → new revision + re-run Inductive|Deductive then Writing.

**Done:** validate exit 0 → proceed to Step 3.

### Step 3 — Narrative arc

Dispatch sibling `narrative-arc-runner` via `$SUBAGENT_TOOL`, then
`$SUBAGENT_AWAIT_SYNC`.

```text
Load {SKILL_ROOT}/compose/narrative-arc-runner/SKILL.md and follow
references/semantic-build-protocol.md then contracts/delivery.md

## Input
REVISION_DIR: <$REVISION_DIR>
PROJECT_ROOT: <abs project root = $(pwd)>
CYCLE_ID: <$CYCLE_ID>
OUTPUT_PATH: _narrative-arc.json
MOUNT: false
```

### Step 4 — Validate narrative arc

```bash
$NARRATIVE_ARC_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --project-root "$(pwd)" \
  --output-path "_narrative-arc.json" \
  --require-write-ready
```

Exit 0 → proceed.
Non-zero → present `$NARRATIVE_ARC_CTL` stderr and exit code to the
parent / human; **stop** Writing.

### Step 5 — Chapter write + assemble

Dispatch sibling `chapter-write-runner` via `$SUBAGENT_TOOL`, then
`$SUBAGENT_AWAIT_SYNC`.

```text
Load {SKILL_ROOT}/compose/chapter-write-runner/SKILL.md and follow
references/write-protocol.md then contracts/delivery.md

## Input
REVISION_DIR: <$REVISION_DIR>
PROJECT_ROOT: <abs project root = $(pwd)>
CYCLE_ID: <$CYCLE_ID>
OUTPUT_DOC_PATH: <$OUTPUT_DOC_PATH>
ARC_PATH: _narrative-arc.json
```

### Step 6 — Validate

Run `$WRITING_COMPOSE_VALIDATE` (prefers `_narrative-arc.json` SoT: arc validity + chapter artifacts + L6; rejects retired `_chapters.json`).

On failure → present `$WRITING_COMPOSE_VALIDATE` stderr and exit code to the
parent / human; **stop** Writing.
On success → Return Summary.

**Done:** `$WRITING_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Writing complete.
  Output: <OUTPUT_DOC_PATH>
  Facts: <REVISION_DIR>/_facts.json (<N> facts; producer-written, validate-only)
  Narrative arc: <REVISION_DIR>/_narrative-arc.json (status=write_ready; <N> sub-topic chapters)
  Chapter artifacts: <REVISION_DIR>/_body-*.txt
  Write-state: <REVISION_DIR>/_chapter-write-state.json (status=complete)
  Scope cross-check: <SCOPE_REF_PATH>
  Draft status: Written
  Next step: parent pause gate (`$POST_WRITING_OPTIONS`)
```
