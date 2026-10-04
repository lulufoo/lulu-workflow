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

Owns Floor / Ceiling / Cascade on intake facts.
Intake, leftover display, and Writing stay with the parent or neighbors.

Floor / Ceiling / Cascade means: `references/derive-semantic-work.md`.

## Input

```text
REVISION_DIR: <abs revision / focus-L; parent binds $DEDUCTIVE_OUT_DIR>
CYCLE_ID: <cycle id>
```

## Cognition

Context terms carry the meanings defined in these units.

| Term | Unit |
|---|---|
| intake facts, `anchors` | `../../references/cognition/fact.md` |
| `section_order`, `section_registry` edges, hole lens | `../../references/cognition/lens.md` |
| published KW table, thin lens | `../../references/cognition/kw-ruler.md` |
| `origin.type=derived`, `ref`, `derive_mode` | `../../references/cognition/producer/provenance.md` |
| projection, hole, never invent | `../../references/cognition/producer/deduce.md` |

One derived fact composes them:

```text
derived(lens) = Project( material facts on upstream edges → lens )
  material   = carried ∪ already derived   (never quarantined / not_needed)
  origin.ref = the projected facts        derive_mode ∈ {floor, ceiling}
  anchors inherited from ref
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$DERIVE_BUILD` | `python3 "$SKILL_ROOT/compose/deductive-runner/derive-runner/scripts/derive_build_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/derive/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$REVISION_DIR"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/facts/facts_control.py"` |

`--help` for each. Scripts never invent derived work-item text.

## Cognitive map

| Layer | Role |
|-------|------|
| **Floor** | Close uncovered derivation edges by projecting known facts onto the hole lens. |
| **Ceiling** | Judge every participant lens against the published KW table and thicken thin ones from existing edges. |
| **Cascade** | Sole persist exit after Ceiling. Owns leftover hole records. |

## Execution

### Prepare
1. Take Input from parent dispatch.
2. `$DERIVE_BUILD context …` (`--help`) → bind:
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
| Ceiling | every participant lens judged; thin lenses got one compensate pass |
| Cascade | persist after scan; Otherwise has the leftover ledger |

## Summary

```text
Derive complete.
  Facts: <path>
  Pending gaps: <n open>
  Status: ok
```
