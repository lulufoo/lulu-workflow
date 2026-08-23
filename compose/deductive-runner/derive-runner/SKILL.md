---
name: derive-runner
description: >-
  Compose deductive L1: Derive Floor + Ceiling (KW ruler) after fact-intake.
---

# derive-runner

Run Derive on intake-classified facts under the published KW ruler. Done when
validate passes. Cascade is the persist exit; leftover edge holes are recorded
only on Otherwise.

## Boundaries

**Out of scope here** (do not perform):

| Do not | Belongs to |
|--------|------------|
| Fact Intake (cut / eval / disposition / confirm) | Upstream `fact-intake-runner` |
| Pending Confirm; disposition-patch / promote | Parent Step 3 |
| Use `$SOURCE_PATH` or re-read upstream prose | Post-intake: facts only |
| Write chapter prose; emit `origin.type=discovered` | Writing / other origin types |

Floor / Ceiling / Cascade means: `references/derive-semantic-work.md`.

## Input

```text
REVISION_DIR: <abs revision / focus-L; parent binds $DEDUCTIVE_OUT_DIR>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$DERIVE_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/deductive-runner/derive-runner/scripts/derive_build_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$REVISION_DIR" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

`--help` for each. Scripts never invent derived work-item text.

## Cognitive map

| Layer | Role |
|-------|------|
| **Floor** | Close edge holes (`edge-scan` + per-lens `append`; no KW; no pending). |
| **Ceiling** | Per required lens: `lens-bundle` → KW judge → one compensate `append`. |
| **Cascade** | After every Ceiling: scan; persist, or rerun Floor→Ceiling, or record leftover then persist. |

## Execution

### Prepare
1. Take Input from parent dispatch.
2. `$DERIVE_BUILD_CTL context …` (`--help`) → bind:
   - `$VAR_LENS_ORDER` ← `section_order`
   - `$VAR_SECTION_REGISTRY` ← `section_registry`

### Derive
3. Load `references/derive-semantic-work.md`; run Floor → Ceiling →
   Cascade as that file defines.

### Persist
4. `$FACTS_CTL validate` (`--help`).

## Done

| Check | Criterion |
|-------|-----------|
| Validate | exit 0 |
| Floor | holes closed in-round or left for Cascade |
| Ceiling | every required lens judged; thin lenses got one compensate pass |
| Cascade | persist after scan; Otherwise has the leftover ledger |

## Summary

```text
Derive complete.
  Facts: <path>
  Pending gaps: <n open>
  Status: ok
```
