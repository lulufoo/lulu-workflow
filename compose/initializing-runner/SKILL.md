---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile pipeline. Loads frameworks;
  validates producer-written `_facts.json` (inductive or deductive); organizes
  chapters; composes per-chapter bodies via fact-first display-layer pipeline
  (Steps 1–5); validates draft quality; persists each chapter incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose Working Rules (Initializing).

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** Step 1 Load → Step 2 Validate facts → Step 3 Narrative arc (phase 1→2) → Step 4 Write-by-sub-topic-chapter then Assemble → Step 5 Validate → Return.

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
| `$SCOPE_REF_PATH` | Absolute path to compose scope SSOT (cross-check only; not atomized here) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`) · `$CODE_GROUNDING` = profile `pipeline.code_grounding` (boolean)

All macros that declare `--profile` **must** pass `--profile "$COMPOSE_PROFILE"` (prefer `--profile` before the subcommand on `$RESOLVE_*`). `$FETCH_COMPOSE` includes `--cycle-id` in the macro.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_ROLE` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" resolve-role --cycle-id "$CYCLE_ID"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" resolve-domain --cycle-id "$CYCLE_ID"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py"` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/init_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/narrative_arc_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_write_state_control.py"` |

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-chapter` · `assemble-arc`.

`$FACTS_CTL` subcommands: `--help` · `write` · `validate` · `status`.

`$NARRATIVE_ARC_CTL` subcommands: `--help` · `validate` · `write` · `show` · `list-chapters`.

`$CHAPTER_WRITE_STATE` subcommands: `--help` · `sync` · `status` · `begin` · `complete` (serial chapter Write gate).

> **K4:** `$INDUCTIVE_FACTS_PROJ project` is **retired**. Do not invoke projection from this runner.

## Execution Contract

### Step 1 — Load

1. `$RESOLVE_ROLE` → Scope Constraints (`### Role Instance`).
2. `$RESOLVE_DOMAIN` → Scope Constraints (`### Domain Instance`).
3. `$FETCH_COMPOSE --role section-registry` (JSON) → `sections` keys (= allowed lenses; `section_order` optional/legacy), `document_preamble`, per-section `heading` / `aliases` / `intent` (else `desc`) / `intent_boundary` / `relations` / `presence`
   `$FETCH_COMPOSE --role section-form-registry` → `sections.{key}.reading_axis` / `presentation` / `expression`
4. `$FETCH_COMPOSE --role section-kw-criteria` → each `## {section_key}` block (Fill completeness for **named** atoms only).
5. Read `$SCOPE_REF_PATH` once for completeness cross-check only (do not atomize).
6. Read profile `pipeline.code_grounding` → `$CODE_GROUNDING`.
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

**Precondition:** Step 3 must produce `_narrative-arc.json` with `status=write_ready`. **Retired (error if present):** `_chapters.json`, `_lens-themes.json`, `_chapter-framework.json`, `_chapter-placement.json`.

**Must:** every non-excluded fact mapped to exactly one arc leaf; every leaf fact in exactly one sub-topic chapter; chapter `lens` ∈ that fact's `lens_tags`; empty `lens_tags` must not reach `write_ready`; before persisting `_body-{cid}.txt`, resolve author-time `F-id` citations; drive 4.W via `$CHAPTER_WRITE_STATE` (one chapter begin→write→complete); run `$INIT_COMPOSE_VALIDATE` before Return.
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

### Step 3 — Narrative arc (phase 1 → phase 2)

Replaces archive-3.0 Dynamic chapter plan. Role/Domain loaded in Step 1 **must** shape content organization here; facts remain the material source.

**Listen-who (arc build):**

| Decision | Listen to | Hardness |
|---|---|---|
| Group/leaf **titles and grouping shape** | Substance story in facts (objects, behaviors, contract surfaces, end-state, verification, …) | **Must** |
| Group/leaf **order** | Role `priority_tendency` | **Must** (exception: fact dependency forces prerequisite first) |
| Intent membership + phase-2 write-unit split | Lens tags + registry lens relations | **Must** (not whole-document leaf order; not presentation title schema) |
| Split / do not mix | Domain `expression_conventions.scannability` (full text for active profile) | **Must** |
| Genre mission / through-line self-check | Domain `cognitive_frame` / `audience_type` | **Should** |

These Role/Domain rules are **agent discipline**. `$NARRATIVE_ARC_CTL validate` still gates coverage / `lens_tags` only — it does **not** enforce the listen-who table.

**Must:** re-read Role `priority_tendency` and Domain `expression_conventions.scannability` before building the arc; name groups/leaves from the substance story; order groups/leaves by `priority_tendency` unless fact structure forces a dependency reorder; obey that Domain `scannability` text when splitting leaves/blocks; keep chapter `lens` ∈ fact `lens_tags`.

**Must not:** use registry lens order as chapter directory; use Role `priority_tendency` (or its information-order list) as a generator of group/leaf titles or a mandatory H2 count; use lens tags/relations as the presentation chapter/title schema (lens-catalog spine); force background / analysis / solution — or any fixed N-act label set — as the **only** allowed top-level packaging (reading aids OK; packaging depth unrestricted); glue two duties into one **top-level** title with 与/及/和 (or English *and* / `&`); use Role `vocabulary_domain` as a taxonomy checklist for group names; invent facts; leave empty `lens_tags` facts in `write_ready`; create `_chapters.json`.

**Top-level title discipline** (`tree` roots only; agent discipline — not `$NARRATIVE_ARC_CTL validate`):

| Principle | Rule |
|---|---|
| Single duty | One chapter duty per top title. Do not glue two duties with 与/及/和 (or English *and* / `&`). |
| Chapter altitude | Top level = through-line chapter stations only. Demote leaf-level concerns to children. |
| Flow | After shape is set, reorder only. Flow never decides split/merge. |

**Conflict exits:** overflow → child under a single-duty parent; never glue titles for flow; never merge unequal altitudes to shorten the path. Group/leaf **order** still follows Role `priority_tendency` (listen-who). Packaging depth stays unrestricted.

#### 3.1 — Phase 1 (`status=mapped`)

1. Read all facts (`$FACTS_CTL` / `_facts.json`). Input = full fact texts + `lens_tags` + registry lens definitions + Role/Domain fields above. Discussion topic / `T*` is provenance only — do not build the spine from it.
2. AI: build narrative arc (optional `tree` packaging; depth unrestricted) and map every non-excluded fact to exactly one **arc leaf** (`leaves[].id` / `title` / `fact_ids`). Composite/pending-split → `excluded` (or `unresolved` if blocked).
3. **Should** self-check before persist: top-level titles look like a lens/priority catalog → rebuild titles/shape; top titles glued with 与/及/和, or too many tops that read as leaf concerns → split or demote (top-level title discipline; do not glue for flow); obvious single-leaf mix that violates Domain `scannability` → split; order badly inverted vs `priority_tendency` with no fact-dependency reason → reorder; optional — outline still matches Domain `cognitive_frame` (genre mission not drifted) and reads as a reviewable through-line for Domain `audience_type` (thicken opening info if needed; do **not** force a fixed three-act directory).
4. Persist:

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
   - Lenses partition write units under a leaf; they do **not** set whole-document leaf order.
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

Keep chapter body shell (`_body-{cid}.txt`); Assemble via `assemble-arc`.

**Presentation layers (archive-5.0):** `tree` group → arc leaf → lens chapter (`cid`). Visible titles stop at group/leaf; lens chapters are anchors + body (default omit lens heading).

Artifacts per write unit (`chapter_id` from `list-chapters`):

```text
_body-{cid}.txt      # body for one (arc-leaf, lens) chapter; no leading ##
```

Visible group/leaf titles come from `_narrative-arc.json` via `assemble-arc`.

#### 4.W — Write-by-sub-topic-chapter

Serial gate (claim-current): `$CHAPTER_WRITE_STATE` owns which chapter is current. Do **not** pick chapters from `list-chapters` / `status.next` for Write.

```bash
$CHAPTER_WRITE_STATE sync --revision-dir "$REVISION_DIR"
```

Loop (claim → write → complete):

```bash
$CHAPTER_WRITE_STATE begin --revision-dir "$REVISION_DIR"
# → work ticket: chapter_id, leaf_id, leaf_title, lens, fact_ids, facts
# already_running → stop; complete current first (do not begin again)
# missing_fact_ids → stop; fix arc/_facts.json (chapter not claimed)
# chapter_id null + status=complete → exit loop
```

For **that ticket only** (`chapter_id` / `fact_ids` / `facts` / `lens` from `begin` stdout):

1. `lens` = ticket.lens; `facts_ℓ` = ticket.facts (authoritative substance — id set must match `fact_ids`; do not expand).
2. Load that lens's **writing cognition** from `section-form-registry` (`reading_axis`, `presentation`, `expression`) — What mechanisms; see `compose-theory.md`.
3. Soft attention (not machine-gated): Domain `expression_conventions`, Role Instance fields, and that cognition's `reading_axis` / `presentation` / `expression` while choosing how to write.
4. Write `_body-{cid}.txt` once for this ticket: content ⊆ `facts_ℓ`; carry anchors (L6); resolve raw `F-id` citations; mark gaps with `> **待决：** …`.

```bash
$CHAPTER_WRITE_STATE complete --revision-dir "$REVISION_DIR"
# → next chapter_id (or null); then loop to begin
```

`complete` hard-gates (same rules re-checked at Step 5): non-empty `_body-{cid}.txt`. On `begin`/`complete` failure → stop; fix artifacts or redo the current chapter; do not skip ahead. Resume: `complete` current if needed, then `begin` again (never `begin --chapter`).

**Must not:** treat `list-chapters` as the 4.W todo list; `begin --chapter` / `complete --chapter` on the main path; Write another chapter while `already_running`.

**Must not (Write substance source):** use memory (including Step 3 full-store recall) as Write fact source; Read `_facts.json` (or any out-of-ticket fetch) for Write; use any substance source other than this round's `begin.facts`.

**Note:** Encourage sectioning in the body. If using heading levels for structure, headings may start at `####`.

#### 4.A — Assemble-from-arc then Close

**Hard gate:** `$CHAPTER_WRITE_STATE` must be `complete` (enforced by `assemble-arc` and Step 5). Do not assemble mid-loop.

One shot (tree packaging + omit lens headings by default):

```bash
$COMPOSE_DOC_CONTROL assemble-arc \
  --path "$OUTPUT_DOC_PATH" \
  --revision-dir "$REVISION_DIR" \
  --preamble "<same substituted document_preamble as Step 1>" \
  --lens-heading omit \
  --tree auto
```

(`--preamble-file` OK for multiline. Overwrites `$OUTPUT_DOC_PATH`. Debug: `--lens-heading show` adds `####` under each anchor.)

**Done:** compose doc has group/leaf visible titles when `tree` present (else leaf `##`); every listed `cid` has `<!-- chapter:{cid} -->` + non-empty body; **no** spine titles of the form `{leaf} · {LENS}` or `Context（CTX）` lens H2/H3.

### Step 5 — Validate

1. `$NARRATIVE_ARC_CTL validate --require-write-ready` (same flags as Step 3).
2. Run `$INIT_COMPOSE_VALIDATE` (prefers `_narrative-arc.json` SoT: arc validity + chapter artifacts + L6; rejects retired `_chapters.json`).
3. On failure → read stderr; **match the first prefix in this order** (then re-run Step 5):

| Order | Prefix / signal | Return to | Action |
|------:|-----------------|-----------|--------|
| 1 | `retired:` | delete file | Remove `_chapters.json` |
| 2 | `3.2:` | **3.2** | Fix arc chapters / tags / unresolved |
| 3 | `4.W:` | **4.W** | Fix write-state (`sync` / finish claim-current begin→complete loop) |
| 4 | `L6:` | **4.W** | Write missing fact-anchor token into that chapter body |
| 5 | `C1:` + derivation / coverage | **Blocking** | Return to parent Inductive|Deductive producer; re-enter Init at Step 2 |
| 6 | `5.A:` | **4.A** | Re-run `assemble-arc` after fixing missing chapter artifacts |

3. On success → Return Summary.

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
