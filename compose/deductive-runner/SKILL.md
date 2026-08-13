---
name: deductive-runner
description: >-
  Compose deductive fact-production orchestrator.
---

# deductive-runner

Orchestrate deductive fact production from source intake through human
confirmation. Done when facts validate, all pending obligations are settled,
and the parent can enter Writing.

## Responsibility

| Area | Boundary |
|------|----------|
| Invocation | Run only from a compose stage `start` on the deductive path. |
| Owns | Fact Intake → Derive → Pending Confirm → Complete. |
| Delegates | `fact-intake-runner` owns cut / eval / disposition / intake Confirm; `derive-runner` owns Floor / Ceiling / Cascade. |
| Downstream | Writing, delivery Eval, and FreeEdit remain with the parent. |

## Cognitive Map

| Concern | Rule |
|---------|------|
| Projection | Project known upstream substance into this stage's required lenses. |
| Stage model | Resolve lenses, Intent, and derivation edges from `section-registry`. |
| State | Facts + pending are the source of truth. |
| Collaboration | AI proposes; the user closes Confirm gates; scripts move state. |

## Invariants

1. After Fact Intake, Steps 2–4 use this stage's facts only; the intake source
   remains unchanged.
2. Produce facts in the active revision; never import upstream `_facts.json` as
   delivery.
3. Apply facts, pending, and disposition mutations through control commands;
   never hand-write state JSON.
4. Preserve user decision ownership: do not invent decisions or label off-edge
   obligations as `derived`.
5. Send every unreferenced quarantined fact through Pending Confirm.

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
| `$CODE_GROUNDING` | Boolean from `enter-producer` stdout |

Bind `$SOURCE_PATH` from `$ATOMIZE_SOURCE_PATH` when only the alias is set.
`$REVISION_DIR` for intake = `$DEDUCTIVE_OUT_DIR`. `$PROJECT_ROOT` = `$(pwd)`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$DEDUCTIVE_OUT_DIR" --project-root "$(pwd)"` |

`$FACTS_CTL` / `$DERIVE_CTL` / `$DEDUCTIVE_CTL`: see each `--help`. Scripts never
invent derived work-item text.

## Execution

**Step 1 Fact Intake → Step 2 Derive → Step 3 Pending Confirm → Step 4 Complete**

### Step 1 — Fact Intake

```bash
$DEDUCTIVE_CTL consume-policy-check
```

Load and follow fact-intake **inline** (interactive Confirm — not a subagent):

```text
Load {SKILL_ROOT}/compose/fact-intake-runner/SKILL.md and follow it.

## Input
REVISION_DIR: <$DEDUCTIVE_OUT_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
```

```bash
$DEDUCTIVE_CTL pending-init
```

**Done:** fact-intake Return Summary `Status: ok`; pending store exists. Proceed to
Step 2.

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

Interactive in this conversation.

Load and follow [Pending Confirm](references/pending-confirm.md):

1. settle unreferenced quarantine;
2. resolve open pending;
3. pass the gate.

**Done:** `gate-check` exits 0. Proceed to Step 4.

### Step 4 — Complete

```bash
$FACTS_CTL validate --revision-dir "$DEDUCTIVE_OUT_DIR" --project-root "$(pwd)"
$DEDUCTIVE_CTL gate-check
```

Return control to the parent compose stage. Parent runs
`$L_STEP complete-producer`, then `$L_STEP enter-writing`.

**Done:** both commands exit 0; `_facts.json` ready for Writing validate-only.

## Return Contract

**Facts:** `_facts.json` — `F-n` with `text`, `lens_tags` (empty for `quarantined` /
`not_needed`), optional `origin` / `derivation` / `source` / `anchors`. Intake
facts: `derivation.disposition` ∈ {`carried`,`quarantined`,`not_needed`};
`not_needed` requires `rule_id` ∈ role `consume_policy.rules[].id`.

**Pending:** `deductive-pending.json` — open/resolved items; schema via
`$DEDUCTIVE_CTL --help`.

**Disposition Confirm (intake):** `{slice}/fact-intake-disposition-review.patch`
(owned by `fact-intake-runner`).

**Post-intake retag patch (optional, Step 3):** agent-chosen path via
`$DEDUCTIVE_CTL disposition-patch-*`.

**Handoff:** return `_facts.json` only; Writing consumes it validate-only.
