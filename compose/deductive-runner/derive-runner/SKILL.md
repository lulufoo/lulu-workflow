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

Means (KW pad, off-edge, batch-retag): `references/derive-semantic-work.md`.

## Input

```text
REVISION_DIR: <abs revision / focus-L; parent binds $DEDUCTIVE_OUT_DIR>
PROJECT_ROOT: <abs project root>
COMPOSE_PROFILE: <profile id>
CYCLE_ID: <cycle id>
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$DERIVE_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/deductive-runner/derive-runner/scripts/derive_build_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

`--help` for each. Scripts never invent derived work-item text.

## Cognitive map

| Layer | Role |
|-------|------|
| **Floor** | Edge-closure **means** (how to close graph holes; no KW). |
| **Ceiling** | Intent projection **means** (how to thicken toward Intent); published **`$VAR_KW_CRITERIA`** = only thickness ruler. |
| **Cascade** | Re-enter Floor then Ceiling when Ceiling creates new holes. |

Edges closed / Intent **should-cover** rows ticked ≠ thick enough. No KW-first pass on
the intake pool.

## Execution

### Prepare
1. Use Input from the parent dispatch (`REVISION_DIR`, …).
2. Run `$DERIVE_BUILD_CTL context …`: bind `$VAR_KW_CRITERIA` ←
   `section_kw_criteria` (KW ruler text). See `--help`.
3. Run `$DERIVE_CTL edge-scan …`: bind `$VAR_EDGE_HOLES` ← `edge_holes`,
   `$VAR_ORDER` ← `order`. See `--help`.

| Var | From |
|-----|------|
| `$VAR_KW_CRITERIA` | context · `section_kw_criteria` |
| `$VAR_EDGE_HOLES` | edge-scan · `edge_holes` |
| `$VAR_ORDER` | edge-scan · `order` |

### Derive
4. Semantic work:
   - Load `references/derive-semantic-work.md`.
   - Run Floor then Ceiling; apply Cascade when new holes appear.
   - Unresolvable gaps → `$DEDUCTIVE_CTL pending-add` (kinds in reference).

### Persist
5. `$DERIVE_CTL append` → `$FACTS_CTL validate` (`--help`).

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
