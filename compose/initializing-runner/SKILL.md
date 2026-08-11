---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile pipeline. Loads frameworks;
  validates producer-written `_facts.json` (inductive or deductive); organizes
  chapters; composes per-chapter bodies via fact-first display-layer pipeline
  (Steps 1–6); validates draft quality; persists each chapter incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose Working Rules (Initializing).

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** Step 1 Load → Step 2 Validate facts → Step 3 Narrative arc → Step 4 Validate narrative arc → Step 5 Chapter write + assemble → Step 6 Validate → Return.

Init is **display-layer only**. Fact production belongs to Inductive|Deductive (`inductive-runner` or `deductive-runner`). Init never Import / Atomize / Derive.

- **Must:** validate producer-written `_facts.json`; place tagged facts; explicit 待决 for gaps; readable chapter bodies.
- **Must not:** invent beyond facts; decide open choices; decision paste; empty shell chapters; recreate `_partition.json`; write `section-key:` anchors (chapter anchors only); invoke retired `$INDUCTIVE_FACTS_PROJ project`; re-run Intake/Derive.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../references/compose-theory.md`](../references/compose-theory.md).

Chapter write contract: [`../references/init-draft-quality.md`](../references/init-draft-quality.md).

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_REF_PATH` | Absolute path to compose scope SSOT (Return echo only; not pre-read here) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`) · `$CODE_GROUNDING` = profile `pipeline.code_grounding` (boolean)

All macros that declare `--profile` **must** pass `--profile "$COMPOSE_PROFILE"`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/init_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |

`$FACTS_CTL` subcommands: `--help` · `write` · `validate` · `status`.

`$NARRATIVE_ARC_CTL` subcommands: `--help` · `validate` · `write` · `show` · `list-chapters` (Step 4 validate; Step 3 delivery via `narrative-arc-runner`).

> **K4:** `$INDUCTIVE_FACTS_PROJ project` is **retired**. Do not invoke projection from this runner.

## Execution Contract

### Step 1 — Load

1. Bind Parent Inputs (`$REVISION_DIR`, `$OUTPUT_DOC_PATH`, `$COMPOSE_PROFILE`, `$CYCLE_ID`, `$SCOPE_REF_PATH` path hold).
2. Resolve `$PROJECT_ROOT` = `$(pwd)`.
3. Read profile `pipeline.code_grounding` → `$CODE_GROUNDING` (do **not** pass to chapter-write-runner).

**Done:** Parent required Inputs bound; `$PROJECT_ROOT` resolved; `$CODE_GROUNDING` boolean set. Do **not** require Role/Domain resolve, section-registry / form-registry / kw-criteria preload, `$SCOPE_REF_PATH` body read, or `init-doc` here. Proceed to Step 2.

---

#### Pipeline invariants (Steps 2–6)

Document spine = `_narrative-arc.json`, **not** registry order / Lens aggregation.

**Precondition:** Step 4 must pass `$NARRATIVE_ARC_CTL validate --require-write-ready` on `_narrative-arc.json`. **Retired (error if present):** `_chapters.json`, `_lens-themes.json`, `_chapter-framework.json`, `_chapter-placement.json`.

**Must:** every non-excluded fact mapped to exactly one arc leaf; every leaf fact in exactly one sub-topic chapter; chapter `lens` ∈ that fact's `lens_tags`; empty `lens_tags` must not reach `write_ready`; run `$INIT_COMPOSE_VALIDATE` before Return.
**Must not:** use `section_order` (or lens list order) as chapter directory; use Role `priority_tendency` / lens tags as presentation chapter titles; force a fixed N-act label set as the only top-level packaging; create or keep `_chapters.json`; decide open choices during Steps 2–3 (待决 same discipline); Import / Atomize / Derive facts.

### Step 2 — Validate facts

Producer (inductive or deductive) already wrote `_facts.json`. **Do not** atomize `$SCOPE_REF_PATH` or Derive. Only validate:

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Missing / invalid `_facts.json` → Blocking (return to parent Inductive|Deductive producer; never re-atomize from scope).

**Structure/fact topology changes:** new revision + re-run Inductive|Deductive (producer) then Init — do not patch `lens_tags` / derivation in place here.

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
COMPOSE_PROFILE: <$COMPOSE_PROFILE>
CYCLE_ID: <$CYCLE_ID>
OUTPUT_PATH: _narrative-arc.json
MOUNT: false
```

### Step 4 — Validate narrative arc

```bash
$NARRATIVE_ARC_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --output-path "_narrative-arc.json" \
  --require-write-ready
```

Exit 0 → proceed. Non-zero → do not continue.

### Step 5 — Chapter write + assemble

Dispatch sibling `chapter-write-runner` via `$SUBAGENT_TOOL`, then
`$SUBAGENT_AWAIT_SYNC`.

```text
Load {SKILL_ROOT}/compose/chapter-write-runner/SKILL.md and follow
references/write-protocol.md then contracts/delivery.md

## Input
REVISION_DIR: <$REVISION_DIR>
PROJECT_ROOT: <abs project root = $(pwd)>
COMPOSE_PROFILE: <$COMPOSE_PROFILE>
CYCLE_ID: <$CYCLE_ID>
OUTPUT_DOC_PATH: <$OUTPUT_DOC_PATH>
ARC_PATH: _narrative-arc.json
```

### Step 6 — Validate

Run `$INIT_COMPOSE_VALIDATE` (prefers `_narrative-arc.json` SoT: arc validity + chapter artifacts + L6; rejects retired `_chapters.json`).

On failure → present `$INIT_COMPOSE_VALIDATE` stderr and exit code to the
parent / human; **stop** Initializing.
On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Initializing complete (narrative-arc display layer).
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Facts: <REVISION_DIR>/_facts.json (<N> facts; producer-written, validate-only)
  Narrative arc: <REVISION_DIR>/_narrative-arc.json (status=write_ready; <N> sub-topic chapters)
  Chapter artifacts: <REVISION_DIR>/_body-*.txt
  Write-state: <REVISION_DIR>/_chapter-write-state.json (status=complete)
  Scope cross-check: <SCOPE_REF_PATH>
  Draft status: Initialized
  Next step: parent pause gate (options from profile pipeline.post_init_options)
```
