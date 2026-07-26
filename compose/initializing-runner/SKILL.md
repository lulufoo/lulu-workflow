---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads frameworks;
  validates producer-written `_facts.json` (inductive or deductive); organizes
  chapters; composes per-chapter bodies via fact-first display-layer pipeline
  (Steps 1–5); validates draft quality; persists each chapter incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** Step 1 Load → Step 2 Validate facts → Step 3 Narrative arc (phase 1→2) → Step 4 Write-by-sub-topic-chapter then Assemble → Step 5 Validate → Return.

Init is **display-layer only**. Fact production belongs to Drafting Step 0 (`inductive-runner` or `deductive-runner`). Init never Import / Atomize / Derive.

- **Must:** validate producer-written `_facts.json`; place tagged facts; explicit 待决 for gaps; readable chapter bodies.
- **Must not:** invent beyond facts; decide open choices; decision paste; empty shell chapters; recreate `_partition.json`; write `section-key:` anchors (chapter anchors only); invoke retired `$INDUCTIVE_FACTS_PROJ project`; re-run Intake/Derive.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../references/compose-theory.md`](../references/compose-theory.md).

Derive artifact contract: [`../references/init-draft-quality.md`](../references/init-draft-quality.md).

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_REF_PATH` | Absolute path to compose scope SSOT (cross-check only; not atomized here) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`) · `$CODE_GROUNDING` = profile `drafting.code_grounding` (boolean)

All macros that declare `--profile` **must** pass `--profile "$COMPOSE_PROFILE"` (prefer `--profile` before the subcommand on `$RESOLVE_*`). `$FACTS_CTL filter` does **not** take `--profile` — pass only `--revision-dir` / `--lens`. `$FETCH_COMPOSE` includes `--cycle-id` in the macro.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" resolve-role --cycle-id "$CYCLE_ID"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" resolve-domain --cycle-id "$CYCLE_ID"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py"` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/init_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/narrative_arc_control.py"` |
| `$CHAPTER_PLAN_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_plan_control.py"` |

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-chapter`.

`$FACTS_CTL` subcommands: `--help` · `write` · `filter` · `validate` · `status`.

`$NARRATIVE_ARC_CTL` subcommands: `--help` · `validate` · `write` · `show` · `list-chapters`.

`$CHAPTER_PLAN_CTL` (legacy archive-3.0 path; not default Init spine): `--help` · `write-themes` · `write-framework` · `propose-placement` · `write-placement` · `list-chapters` · `validate`.

> **K4:** `$INDUCTIVE_FACTS_PROJ project` is **retired**. Do not invoke projection from this runner.

## Execution Contract

### Step 1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE --role section-registry` (JSON) → `sections` keys (= allowed lenses; `section_order` optional/legacy), `document_preamble`, per-section `heading` / `aliases` / `intent` (else `desc`) / `intent_boundary` / `relations` / `presence`
   `$FETCH_COMPOSE --role section-form-registry` → `sections.{key}.presentation` / `expression`
4. `$FETCH_COMPOSE --role section-kw-criteria` → each `## {section_key}` block (Fill completeness for **named** atoms only).
5. Read `$SCOPE_REF_PATH` once for completeness cross-check only (do not atomize).
6. Read profile `drafting.code_grounding` → `$CODE_GROUNDING`.
7. **Init document:** Substitute placeholders in `document_preamble`. Write via:

```bash
$COMPOSE_DOC_CONTROL init-doc \
  --path "$OUTPUT_DOC_PATH" \
  --preamble "<substituted document_preamble markdown>"
```

Prefer `--preamble-file` when content is multiline.

**Done:** `$OUTPUT_DOC_PATH` exists with preamble only. Proceed to Step 2.

---

#### Pipeline invariants (Steps 2–5)

Allowed lenses = `section-registry.sections` keys (archive-5.0). Document spine = `_narrative-arc.json`, **not** registry order / Lens aggregation.

**Precondition:** Step 3 must produce `_narrative-arc.json` with `status=write_ready`. **`_chapters.json` is retired.** Legacy `_lens-themes.json` / `_chapter-framework.json` / `_chapter-placement.json` are **not** the default Init spine.

**Must:** every non-excluded fact mapped to exactly one arc leaf; every leaf fact in exactly one sub-topic chapter; chapter `lens` ∈ that fact's `lens_tags`; empty `lens_tags` must not reach `write_ready`; before persisting `_body-{cid}.txt`, resolve author-time `F-id` citations; run `$INIT_COMPOSE_VALIDATE` before Return.
**Must not:** use `section_order` (or lens list order) as chapter directory; create or keep `_chapters.json`; decide open choices during Steps 2–3 (待决 same discipline); Import / Atomize / Derive facts.

### Step 2 — Validate facts

Producer (inductive or deductive) already wrote `_facts.json`. **Do not** atomize `$SCOPE_REF_PATH` or Derive. Only validate:

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Missing / invalid `_facts.json` → Blocking (return to parent Drafting Step 0 producer; never re-atomize from scope).

**Structure/fact topology changes:** new revision + re-run Drafting Step 0 (producer) then Init — do not patch `lens_tags` / derivation in place here.

**Done:** validate exit 0 → proceed to Step 3.

### Step 3 — Narrative arc (phase 1 → phase 2)

Replaces archive-3.0 Dynamic chapter plan. Contract: `docs/domain/archive/compose/archive-5.0/compose-narrative-arc-lens-v2-landing-design.md`.

**Must not:** use registry lens order as chapter directory; invent facts; leave empty `lens_tags` facts in `write_ready`; create `_chapters.json`.

#### 3.1 — Phase 1 (`status=mapped`)

1. Read all facts (`$FACTS_CTL` / `_facts.json`). Input = full fact texts + `lens_tags` + registry lens definitions. Discussion topic / `T*` is provenance only — do not build the spine from it.
2. AI: build narrative arc (optional `tree` packaging; depth unrestricted) and map every non-excluded fact to exactly one **arc leaf** (`leaves[].id` / `title` / `fact_ids`). Composite/pending-split → `excluded` (or `unresolved` if blocked).
3. Persist:

```bash
$NARRATIVE_ARC_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --file "<path to arc JSON with status=mapped>"
```

```bash
$NARRATIVE_ARC_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

**Done (3.1):** `_narrative-arc.json` exists; `status=mapped`; coverage + single-leaf ownership pass.

#### 3.2 — Phase 2 (`status=write_ready`)

1. For each arc leaf, partition its `fact_ids` into **sub-topic chapters** `{lens, fact_ids}`:
   - One fact → exactly one chapter under that leaf.
   - Chapter `lens` **must be ∈** that fact's `lens_tags` (single tag → that lens; multi-tag → AI picks one).
   - Empty `lens_tags` → `unresolved` / hard fail — never `write_ready`.
2. Set `status=write_ready` only when `unresolved` is empty and validation passes.
3. Persist + gate:

```bash
$NARRATIVE_ARC_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --file "<path to arc JSON with status=write_ready>"
```

```bash
$NARRATIVE_ARC_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --require-write-ready
```

**Done (Step 3):** `_narrative-arc.json` with `status=write_ready`; `$NARRATIVE_ARC_CTL list-chapters` succeeds.

### Step 4 — Write-by-sub-topic-chapter then Assemble

Keep chapter delivery shell (`_derive-{cid}.json`, `_body-{cid}.txt`, `append-chapter`).

Artifacts per write unit (`chapter_id` from `list-chapters`):

```text
_derive-{cid}.json   # display_title + lens
_body-{cid}.txt      # ## omitted; body for one (arc-leaf, lens) chapter
```

#### 4.W — Write-by-sub-topic-chapter

```bash
$NARRATIVE_ARC_CTL list-chapters \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

For each unit in `chapters[]` order:

1. `lens` = unit.lens; `facts_ℓ` = facts whose id ∈ unit.fact_ids (authoritative — do not expand).
2. Load Write form for `lens` from section-form-registry / registry intent.
3. **Derive F** (S1): same F discipline as prior Init (carrier/structure from form + facts).
4. **Derive C** (S1): `c[]` from domain `expression_conventions`, Role Fields, and this lens's `expression` (traceable). **C is constrained by F**.
5. **Write body:** Scaffold per F; obey every C; content ⊆ `facts_ℓ`; carry anchors (L6); resolve raw `F-id` citations; mark gaps with `> **待决：** …`.
   **Do not Write until F and C Done for this unit.**

**Note:** Encourage sectioning in the body. If using heading levels for structure, headings may start at `####`.

#### 4.A — Assemble-by-chapter then Close

Render order = `$NARRATIVE_ARC_CTL list-chapters` → `chapter_ids`.

For each `cid` in that order:

1. `display_title` ← unit.display_title (leaf title · lens); do not invent at assemble time.
2. Body = the unit body from 4.W (one sub-topic chapter per cid).
3. Write `_derive-{cid}.json` (`display_title`, `lens`) and `_body-{cid}.txt`.
4. Close:

```bash
$COMPOSE_DOC_CONTROL append-chapter \
  --path "$OUTPUT_DOC_PATH" \
  --chapter-id "{cid}" \
  --revision-dir "$REVISION_DIR"
```

**Hard gate:** any unit missing F/C/body → do not append that chapter.

**Done:** every listed chapter has `<!-- chapter:{cid} -->` and non-empty rendered content. Flat `## {display_title}` from `_derive-{cid}.json`.

### Step 5 — Validate

1. `$NARRATIVE_ARC_CTL validate --require-write-ready` (same flags as Step 3).
2. Run `$INIT_COMPOSE_VALIDATE` (prefers `_narrative-arc.json` SoT: arc validity + chapter artifacts + L6; rejects retired `_chapters.json`).
3. On failure → read stderr; **match the first prefix in this order** (then re-run Step 5):

| Order | Prefix / signal | Return to | Action |
|------:|-----------------|-----------|--------|
| 1 | `retired:` | delete file | Remove `_chapters.json` |
| 2 | `3.2:` | **3.2** | Fix arc chapters / tags / unresolved |
| 3 | `L6:` | **4.W** | Write missing fact-anchor token into that chapter body |
| 4 | `C1:` + derivation / coverage | **Blocking** | Return to parent Drafting Step 0 producer; re-enter Init at Step 2 |
| 5 | `5.A:` | **4.A** | Re-assemble / `append-chapter` for `list-chapters` only |

3. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Initializing complete (narrative-arc display layer).
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Facts: <REVISION_DIR>/_facts.json (<N> facts; producer-written, validate-only)
  Narrative arc: <REVISION_DIR>/_narrative-arc.json (status=write_ready; <N> sub-topic chapters)
  Chapter artifacts: <REVISION_DIR>/_derive-*.json, _body-*.txt
  Scope cross-check: <SCOPE_REF_PATH>
  Draft status: Initialized
  Next step: parent pause gate (options from profile drafting.post_init_options)
```
