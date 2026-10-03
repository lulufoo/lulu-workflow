---
name: deductive-runner
description: >-
  Compose deductive fact-production orchestrator.
---

# deductive-runner

Orchestrate deductive fact production from already-intaken facts. Done
when facts validate and the parent can enter Writing.

## Responsibility

| Area | Boundary |
|------|----------|
| Invocation | Run only from compose L-execution on the deductive path. |
| Owns | pending-init → Derive → Pending Confirm → Complete. `$FAST_COMPLETE` true skips Derive and Confirm. |
| Delegates | `derive-runner` owns Floor / Ceiling / Cascade. |
| Downstream | Writing, delivery Eval, and FreeEdit remain with the parent. |

## Cognition

Facts and their fields carry the meanings defined in these units.

| Term | Unit |
|---|---|
| deduction, projection, hole, leftover | `../references/cognition/producer/deduce.md` |
| fact, `lens`, `anchors` | `../references/cognition/fact.md` |
| lens, `section-registry` edges | `../references/cognition/lens.md` |
| `origin` (`derived`), `derivation.disposition` | `../references/cognition/producer/provenance.md` |
| role `consume_policy` | `../references/cognition/profile/role.md` |

Derive material is the carried intake facts plus facts already derived;
quarantined and not_needed facts are provenance records, not material.
Facts and pending are the source of truth. When `$FAST_COMPLETE` is false,
the AI shows leftovers and the user confirms once; scripts move state.

## Invariants

1. Steps use this stage's facts only; the intake source remains unchanged.
2. Produce facts in the active revision; never import upstream `_facts.json` as
   delivery.
3. Apply facts, pending, and disposition mutations through control commands;
   never hand-write state JSON.
4. Preserve user decision ownership: do not invent decisions or label off-edge
   obligations as `derived`.
5. When `$FAST_COMPLETE` is false, show unreferenced quarantined ids and leftover `edge_hole` links.

## Inputs

| Var | Meaning |
|-----|---------|
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_REF` | Upstream scope structure ref |
| `$SOURCE_PATH` | Absolute intake SoT doc (fact-intake SoT); format-neutral |
| `$ATOMIZE_SOURCE_PATH` | Retired alias of `$SOURCE_PATH` (same path when present) |
| `$INTENT_BASELINE_REFS` | JSON array of classified, read-only intent baseline refs; not intake input |
| `$NORM_CONSTRAINT_REFS` | JSON array of classified, read-only norm constraint refs; not intake input |
| `$DEDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) |
| `$CODE_GROUNDING` | Boolean from `enter-deductive` stdout |

Bind `$SOURCE_PATH` from `$ATOMIZE_SOURCE_PATH` when only the alias is set.
`$PROJECT_ROOT` = `$(pwd)`. Parent has already completed Fact Intake.

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/facts/facts_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/derive/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR" --project-root "$(pwd)"` |

`$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL`: see each `--help`. Scripts never
invent derived work-item text.

## Execution

**Step 1 Preflight → Step 2 Derive → Step 3 Pending Confirm → Step 4 Complete**

### Step 1 — Preflight

```bash
$DEDUCTIVE_CTL pending-init
```

Bind `$FAST_COMPLETE` from stdout `fast_complete`.

**Done:** exit 0; pending store exists. `$FAST_COMPLETE` true → Step 4. Else Step 2.

### Step 2 — Derive

Dispatch nested `derive-runner` via `$SUBAGENT_TOOL`, then
`$SUBAGENT_AWAIT_SYNC`.

```text
Load {SKILL_ROOT}/compose/deductive-runner/derive-runner/SKILL.md and follow it.

## Input
REVISION_DIR: <$DEDUCTIVE_OUT_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
CYCLE_ID: <$CYCLE_ID>
```

**Done:** derive-runner Summary `Status: ok`. Proceed to Step 3.

### Step 3 — Pending Confirm

Interactive. Show leftovers, then one confirm.

1. `$DEDUCTIVE_CTL quarantine-unref` → count and ids
2. `$DEDUCTIVE_CTL pending-list` → each open `edge_hole` as `lens ←` uncovered ids
3. Ask once to end Deductive.

```text
Unreferenced quarantine: <n>
  <F-id> …
edge_hole links: <n>
  <lens> ← <F-id>, …
```

Zero counts still show the heading.

**Done:** user confirmed. Proceed to Step 4.

### Step 4 — Complete

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --project-root "$(pwd)"
$DEDUCTIVE_CTL gate-check
```

Return control to the parent compose stage. Parent runs
`$EXECUTION complete-deductive`, then `$EXECUTION enter-writing`.

**Done:** both commands exit 0; `_facts.json` ready for Writing validate-only.

## Return Contract

**Facts:** `_facts.json` — `F-n` with `text`, `lens` (omitted for `quarantined` /
`not_needed`), optional `origin` / `derivation` / `source` / `anchors`. Intake
facts: `derivation.disposition` ∈ {`carried`,`quarantined`,`not_needed`};
`not_needed` requires `rule_id` ∈ role `consume_policy.rules[].id`.

**Pending:** `deductive-pending.json` — open/resolved items; schema via
`$DEDUCTIVE_CTL --help`.

**Disposition Confirm (intake):** `{slice}/fact-intake-disposition-review.patch`
(owned by `fact-intake-runner`).

**Handoff:** return `_facts.json` only; Writing consumes it validate-only.
