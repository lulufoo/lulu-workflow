---
name: fact-intake-runner
description: >-
  Compose fact-intake orchestrator: doc → cut → intake eval → disposition
  classify → confirm → usable _facts.json for inductive and deductive callers.
---

# fact-intake-runner

Turn `$SOURCE_PATH` into a validated, disposition-classified focus-slice
`_facts.json` shared by inductive and deductive producers.

**Must:** bind Parent Inputs; dispatch L1 cut → structural validate → L1 intake
eval → L1 disposition → inline Confirm; return only when DONE.  
**Must not:** Derive / Shape / G2 / G3 / `fact-store-runner`; edit `$SOURCE_PATH`;
fetch registry/role in parent Load (L1 self-`context`).

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute revision / focus-L root |
| `$PROJECT_ROOT` | Project root; default `$(pwd)` |
| `$COMPOSE_PROFILE` | Compose profile id |
| `$CYCLE_ID` | Active cycle id |
| `$SOURCE_PATH` | Absolute intake SoT doc (Eval SoT) |

Caller binds `$SOURCE_PATH`: deductive = former `$ATOMIZE_SOURCE_PATH`; inductive =
L mirror `source_path` (not scope-package whole).

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$FACT_INTAKE_DISPOSITION_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/scripts/fact_intake_disposition_control.py"` |

`$FACTS_CTL`: `--help` · `validate` · `status` · `write`.  
Disposition patch: `--help` · `disposition-patch-validate` · `disposition-patch-apply`.

## Execution

### Step 1 — Load

Bind Parent Inputs. Resolve `$PROJECT_ROOT` = `$(pwd)` when omitted.  
**Done:** required Inputs bound → Step 2.

### Step 2 — Cut (L1 subagent)

Dispatch nested `fact-cut-runner` via `$SUBAGENT_TOOL`, then `$SUBAGENT_AWAIT_SYNC`.

```text
Load {SKILL_ROOT}/compose/fact-intake-runner/fact-cut-runner/SKILL.md and follow it.

## Input
REVISION_DIR: <$REVISION_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
COMPOSE_PROFILE: <$COMPOSE_PROFILE>
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
```

### Step 3 — Validate (pre-Eval)

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --intake-structure
```

Inductive callers add `--require-seed-origin`. Exit 0 → Step 4.

### Step 4 — Intake Eval (L1 subagent)

Dispatch nested `fact-intake-eval` via `$SUBAGENT_TOOL`, then `$SUBAGENT_AWAIT_SYNC`.

```text
Load {SKILL_ROOT}/compose/fact-intake-runner/fact-intake-eval/SKILL.md and follow it.

## Input
REVISION_DIR: <$REVISION_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
COMPOSE_PROFILE: <$COMPOSE_PROFILE>
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
```

**Done:** `eval_status=done`. Remediation edits `_facts.json` only (no re-Cut).

### Step 5 — Disposition (L1 subagent)

Dispatch nested `fact-disposition-runner` via `$SUBAGENT_TOOL`, then
`$SUBAGENT_AWAIT_SYNC`.

```text
Load {SKILL_ROOT}/compose/fact-intake-runner/fact-disposition-runner/SKILL.md and follow it.

## Input
REVISION_DIR: <$REVISION_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
COMPOSE_PROFILE: <$COMPOSE_PROFILE>
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
```

### Step 6 — Disposition Confirm (parent inline)

Draft Confirm patch **next to** `_facts.json` (active slice; not revision root
when a discussion pointer is set). Resolve path, then draft op-list:

```bash
$FACT_INTAKE_DISPOSITION_CTL disposition-patch-path \
  --revision-dir "$REVISION_DIR"
# → .path (same directory as .facts_path)
```

Chat: path + counts + accept / edit / reject — not full id dumps.

```bash
# --patch-file optional; defaults to {active slice}/fact-intake-disposition-review.patch
$FACT_INTAKE_DISPOSITION_CTL disposition-patch-validate \
  --revision-dir "$REVISION_DIR"
# after user accept:
$FACT_INTAKE_DISPOSITION_CTL disposition-patch-apply \
  --revision-dir "$REVISION_DIR"
```

Empty ops / no-change: user confirms explicitly. This wave: edit patch in parent
(do not kick back to disposition-runner; see framework O7).

### Step 7 — Return

## Return Summary

```text
Fact-intake complete.
  Profile: <COMPOSE_PROFILE>
  Source: <SOURCE_PATH>
  Facts: <abs path to _facts.json>
  Eval: done
  Disposition: done
  Disposition-confirm: done
  Status: ok|failed
```
