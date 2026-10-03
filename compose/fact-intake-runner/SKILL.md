---
name: fact-intake-runner
description: >-
  Compose fact-intake orchestrator: intake document to classified
  focus-slice facts.
---

# fact-intake-runner

Turn `$SOURCE_PATH` into classified focus-slice facts. Done when Confirm
apply exits 0.

**Must:** bind Parent Inputs; dispatch L1; `$FACTS_CTL validate
--require-derivation`; inline Confirm.  
**Must not:** Derive / Shape / G2 / G3 / `fact-store-runner`; edit
`$SOURCE_PATH`; fetch registry/role in parent Load.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute revision root |
| `$PROJECT_ROOT` | Project root; default `$(pwd)` |
| `$CYCLE_ID` | Active cycle id |
| `$SOURCE_PATH` | Absolute intake SoT doc |
| `$REQUIRE_SEED_ORIGIN` | Optional; `true` adds `--require-seed-origin` on write/validate |

Parent binds `$SOURCE_PATH` and `$REQUIRE_SEED_ORIGIN`.

## Script Macros

Contract in `--help`.

| Macro | Command |
|---|---|
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/facts/facts_control.py"` |
| `$FACT_INTAKE_DISPOSITION_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/scripts/fact_intake_disposition_control.py"` |

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
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
REQUIRE_SEED_ORIGIN: <$REQUIRE_SEED_ORIGIN>
```

### Step 3 — Validate

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --project-root "$(pwd)" \
  --require-derivation
# when REQUIRE_SEED_ORIGIN=true, also pass --require-seed-origin
```

Exit 0 → Step 4.

### Step 4 — Confirm

```bash
$FACT_INTAKE_DISPOSITION_CTL disposition-patch-path \
  --revision-dir "$REVISION_DIR"
```

Bind `.path` from stdout. Chat: path + counts + accept / edit / reject.

```bash
$FACT_INTAKE_DISPOSITION_CTL disposition-patch-validate \
  --revision-dir "$REVISION_DIR"
# after user accept:
$FACT_INTAKE_DISPOSITION_CTL disposition-patch-apply \
  --revision-dir "$REVISION_DIR"
```

Empty ops: user confirms explicitly. This wave: edit the patch in parent.

### Step 5 — Return

```text
Fact-intake complete.
  Source: <SOURCE_PATH>
  Facts: <abs path from validate stdout>
  Disposition: done
  Disposition-confirm: done
  Status: ok|failed
```
