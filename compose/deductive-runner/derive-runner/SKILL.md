---
name: derive-runner
description: >-
  Compose deductive L1: Derive Floor + Ceiling (KW ruler) after fact-intake.
---

# derive-runner

Run Derive on intake-classified facts under the published KW ruler. Done when
validate passes and every floor hole / required lens is covered or pending.

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
| **Floor** | Close edge holes (`edge-scan` + per-lens `append`; no KW). |
| **Ceiling** | Per required lens: `lens-bundle` → KW judge → Means/`append`. |
| **Cascade** | Only after Ceiling `append`: fresh holes? → Floor then full Ceiling. |

## Execution

### Prepare
1. Take Input from parent dispatch.
2. `$DERIVE_BUILD_CTL context …` (`--help`) → bind:
   - `$VAR_LENS_ORDER` ← `section_order`
   - `$VAR_SECTION_REGISTRY` ← `section_registry`

### Derive
3. Load `references/derive-semantic-work.md`; run Floor Loop → Ceiling →
   Cascade as that file defines.
4. Open gaps → `$DEDUCTIVE_CTL pending-add` (kinds in the reference).

### Persist
5. `$FACTS_CTL validate` (`--help`).

## Done

| Check | Criterion |
|-------|-----------|
| Validate | exit 0 |
| Floor | every hole covered or pending |
| Ceiling | every required lens KW-satisfied or open `kw_shortfall` / other pending |

## Summary

```text
Derive complete.
  Facts: <path>
  Pending gaps: <n open>
  Status: ok
```
