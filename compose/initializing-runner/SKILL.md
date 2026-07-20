---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads upstream scope
  doc and frameworks; atomizes facts (or validates discovery-written inductive
  `_facts.json`); organizes chapters; composes per-chapter bodies via fact-first
  display-layer pipeline (Steps 1–6); validates draft quality; persists each
  chapter incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** Step 1 Load → Step 2 Atomize facts (inductive: validate discovery-written `_facts.json` only; deductive: atomize scope) → Step 3 Derive facts → Step 4 Dynamic chapter plan (themes → framework → placement) → Step 5 Write-by-FL then Assemble chapters → Step 6 Validate → Return.

Init substance: display-layer Steps 2–6. Inductive discovery loop owns `_facts.json` as engine state (K4; no projection). Deductive Init atomizes scope into facts.

- **Must:** operationalize display-layer facts (inductive: validate-only on discovery-written `_facts.json`; deductive: atomize scope); explicit 待决 for gaps; readable chapter bodies.
- **Must not:** invent beyond facts/scope/upstream-derivation sources; decide open choices during derivation; decision paste; empty shell chapters; recreate `_partition.json` or reassemble fact text by hand; write `section-key:` anchors (chapter anchors only); invoke retired `$INDUCTIVE_FACTS_PROJ project`.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../references/compose-theory.md`](../references/compose-theory.md).

Derive artifact contract: [`../references/init-draft-quality.md`](../references/init-draft-quality.md).

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_REF_PATH` | Absolute path to compose scope SSOT (decision holders: `decision-fact.json` required; plan←design may be design-doc) |
| `$SCOPE_FACTS_PATH` | Absolute path to upstream fact package (design `_facts.json`); empty when upstream has no fact package |
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
| `$CHAPTER_PLAN_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_plan_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` (K1 Step 3 mechanical shell) |
| `$DECISION_FACT_CLAIM_CTL` | `python3 "$SKILL_ROOT/compose/scripts/core/decision_fact_claim_control.py" --revision-dir "$REVISION_DIR"` |

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-chapter`.

`$FACTS_CTL` subcommands: `--help` · `write` · `filter` · `validate` · `status`.

`$CHAPTER_PLAN_CTL` subcommands: `--help` · `write-themes` · `write-framework` · `propose-placement` · `write-placement` · `list-chapters` · `validate`.

`$DERIVE_CTL` subcommands: `--help` · `plan` · `append` · `audit` · `classify`. Scripts never invent derived text — only triggers / topo-order / id append / self-audit.

> **K4:** `$INDUCTIVE_FACTS_PROJ project` is **retired**. Inductive `_facts.json` is written by the discovery loop (`seed-decision` / `settle-open`). Do not invoke projection from this runner.

## Execution Contract

### Step 1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE --role section-registry` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `aliases` / `intent` (else `desc`) / `intent_boundary` / `relations` / `presence` (used at Step 4)
   `$FETCH_COMPOSE --role section-form-registry` → `sections.{key}.presentation` / `expression`
4. `$FETCH_COMPOSE --role outline-registry` → `candidates` / `rules` as **optional seed/heuristic only** (S-gen). Step 4 topology SSOT is dynamic themes→framework, not keep-isomorphic candidates.
5. `$FETCH_COMPOSE --role section-kw-criteria` → each `## {section_key}` block (Fill completeness for **named** atoms only).
6. Read `$SCOPE_REF_PATH` once (JSON units or prose, depending on artifact).
7. Read profile `drafting.code_grounding` → `$CODE_GROUNDING`.
8. **Init document:** Substitute placeholders in `document_preamble`. Write via:

```bash
$COMPOSE_DOC_CONTROL init-doc \
  --path "$OUTPUT_DOC_PATH" \
  --preamble "<substituted document_preamble markdown>"
```

Prefer `--preamble-file` when content is multiline.

Do **not** append outline-registry content to the deliverable header. Do **not** fetch spec-template URLs.

**Done:** `$OUTPUT_DOC_PATH` exists with preamble only. Proceed to Step 2.

---

#### Pipeline invariants (Steps 2–6)

`section_order` means the profile's *lens* set (same registry, reframed as intent lenses — see [Theory](../references/compose-theory.md)).

**Precondition:** Step 4 must produce `_lens-themes.json` + `_chapter-framework.json` + `_chapter-placement.json`. Outline `candidates`/`rules` are optional seed only. **`_chapters.json` is retired** — must not exist under `$REVISION_DIR`.

**Handshake with `drafting.inductive` (K4):** operative branch is Step 2 Branch A (validate-only; never re-atomize).

**Must:** tag every atom with N:M `lens_tags` (zero, one, or many — never a single `home`); run Step 3 for zero-coverage required derivation lenses before Step 4; place every fact with non-empty `lens_tags` exactly once in `_chapter-placement.json`; before persisting `_body-{cid}.txt`, resolve every author-time `F-id` citation into a human-readable chapter reference (write-side — `$INIT_COMPOSE_VALIDATE` does **not** scan for raw `F-id`); run `$INIT_COMPOSE_VALIDATE` before Return.
**Must not:** write a `fact:` or `section-key:` anchor into `$OUTPUT_DOC_PATH` (chapter anchors only); create or keep `_chapters.json`; decide open choices during Steps 2/3/4 (待决 same discipline).

### Step 2 — Atomize facts

**Branch A — inductive profile (`drafting.inductive=true`, K4):** discovery loop already wrote `_facts.json` (`seed-decision` / `settle-open`). **Do not** atomize `$SCOPE_REF_PATH`. Only validate:

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Missing / invalid `_facts.json` → Blocking (never re-atomize from scope). **Done:** validate exit 0 → proceed to Step 3.

**Branch B — deductive / non-inductive (`drafting.inductive` absent/false):**

1. **Materialize candidates** (exactly one branch; no new step number):
   - If `$SCOPE_FACTS_PATH` is non-empty → **Import**: read that `_facts.json`. For each upstream fact: assign a new contiguous local `F-n` (do not reuse upstream ids); keep `text` and `origin` (when present) verbatim; never carry upstream `lens_tags`. Match against this stage's Intent SSOT (`intent` else `desc`, `intent_boundary` when present): match → retag Plan `lens_tags` + `derivation.disposition="carried"`; no match → empty `lens_tags` + `derivation.disposition="quarantined"`. Always set `derivation.upstream_ref` to the upstream Design F-id(s).
   - Else if `$SCOPE_REF_PATH` is `decision-fact.json` → **Unit-import**: `$DECISION_FACT_CLAIM_CTL ensure`. Read units from `$SCOPE_REF_PATH`. For each unit pulled into this stage's lenses: `set-status --status claimed --by init` → emit a local fact `{text, origin:{type:seed, ref:[unit-id]}, lens_tags}` → `set-status --status settled --by init` (same pass). Units left unclaimed stay on the claim ledger (`check`); do not silently drop.
   - Else (`$SCOPE_FACTS_PATH` empty and `$SCOPE_REF_PATH` is prose) → **Atomize** `$SCOPE_REF_PATH` once (whole doc) — merge same-fact restatements into one atom; do not split by source section; a figure is one atom, kept intact. (Tags are applied in sub-step 2.)
2. **Tag / verify `lens_tags`:**
   - **Prose-line (Atomize):** for each atom, choose the set (zero, one, or many) of `section_order` keys whose intent the atom answers — using registry projection only. N:M: an atom may tag no lens (quarantine candidate, audited by Q1), one lens, or several.
   - **Fact-line (Import):** **verify-only** — check `derivation.disposition`↔`lens_tags` (`carried`⇔non-empty, `quarantined`⇔empty). Do **not** re-run match logic.
   - **Unit-import:** tag while importing (consumer lens map under I4); treat like Prose-line for Q1 quarantine rules.
3. **Persist** via `$FACTS_CTL write` (facts = JSON array `{id:F-n, text, lens_tags}` — optional `origin` / `derivation` for Import; optional `source` only for Step-3-derived facts later; Prose-line Step 2 atoms omit `source`/`derivation`; Unit-import carries `origin.type=seed` + `origin.ref=[unit-id]`):

```bash
$FACTS_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --facts-file "<path to facts JSON>"
```

4. `$FACTS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0.

**Import mis-match correction:** FreeEdit Tier A must **not** retag `lens_tags` / chapter placement to “fix” Import match vs quarantine. Correction path is FreeEdit Tier B — new revision, re-run Steps 2–6 (full re-Init).

**Done (Branch B):** `$REVISION_DIR/_facts.json` exists and validates — **Step 2 atoms only**; Step 3 may append derived facts before Step 4.

### Step 3 — Derive facts（演绎派生，仅有派生边的 required 视角）

Runs **between** Step 2 and Step 4. **Step 3 = AI semantic step + mechanical shell** (`$DERIVE_CTL`): CLI decides *which* lenses trigger and how ids append; **you** project work-item text from upstream **facts** (never prose).

**Must (CLI shell first):**
1. **Snapshot Step 2** (for audit): copy `$REVISION_DIR/_facts.json` → a temp `pre-derive-facts.json`.
2. **Plan triggers** (zero-only + topo order + true gaps):

```bash
$DERIVE_CTL plan \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Use stdout `order` (upstream-first). `true_gaps` → flag Round; do **not** invent. Partial coverage (`facts>0`) never appears in `triggered`. Cycle → Blocking (non-zero exit).
**If `order` is empty:** skip Emit / `$DERIVE_CTL append` / `$DERIVE_CTL audit`; run `$FACTS_CTL validate` only → Step 3 Done (no derivation lenses fired).
3. **Input:** for each `L` in `order`, read upstream facts from plan stdout `upstreams[L].upstream_facts` (or `$FACTS_CTL filter --revision-dir "$REVISION_DIR" --lens U` — no `--profile`). Optional code grounding when `$CODE_GROUNDING` is true. **Do not** read `_body` / `.md` prose.
4. **Emit (AI):** each work item → one object `{text, lens_tags:[L], source?}` (prefer upstream `F-id`s in `source`; freeform anchors allowed; no F-id integrity check). Undecided → embed `待决：…` in `text` (or a 待决 fact), never invent a choice. Write the array to a temp `derived.json`. Same-pass cascade: later lenses **see** facts you already decided for earlier lenses in `order`.
5. **Append once** (contiguous `F-(k+1)..`):

```bash
$DERIVE_CTL append \
  --revision-dir "$REVISION_DIR" \
  --derived-file "<path to derived.json>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

6. **Self-audit** (cascade-aware; Blocking on fail):

```bash
$DERIVE_CTL audit \
  --revision-dir "$REVISION_DIR" \
  --before-file "<path to pre-derive-facts.json>" \
  --triggered "<comma-separated order from plan>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Empty upstream → audit skips that lens; C1 at Step 6 is the backstop.
7. `$FACTS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0.

**Must not:** decide open choices; read prose; write facts for non-triggered lenses; strip/re-derive by `source` in-place (re-derive ⇒ full re-run — inductive: **Blocking** — return to inductive-runner to `seed-decision` / `settle-open` missing substance, then re-enter Init at Step 2 Branch A; do **not** run retired projection; deductive: re-run Step 2 then Step 3); skip `$DERIVE_CTL plan` when deriving; invent triggers or ids by hand. When `order` is non-empty, do not skip `append` / `audit`.

**Done:** `_facts.json` includes any Step-3-derived facts; when `order` was non-empty, `$DERIVE_CTL audit` exit 0; `$FACTS_CTL validate` exit 0.

### Step 4 — Dynamic chapter plan (themes → framework → placement)

Process contract: `docs/domain/archive/compose/archive-3.0/compose-init-dynamic-chapter-framework-design.md`.

**Must not:** dump full `_facts.json` into one model pass to invent themes; invent topology without 4.A→4.B→4.C; create `_chapters.json` (retired).

#### 4.A — Lens → theme + desc (SKILL loop; script filter)

1. `$FACTS_CTL status --revision-dir "$REVISION_DIR"` → lenses to cover (`by_lens` ∪ required lenses from `section_presence_map`).
2. For each lens `ℓ` (uppercase key):  
   `facts_ℓ ← $FACTS_CTL filter --revision-dir "$REVISION_DIR" --lens ℓ`  
   Induct one `{form_lens_id: FL-n, lens_key: ℓ, theme, desc}` — **only** from that filter output.  
   - `theme`: short H3-ready title (one line).  
   - `desc`: 1–3 sentences for clustering (not draft prose; not a fact dump).  
   - Empty filter (required, zero facts): `theme`/`desc` may be `（待补）…` — do not invent propositions.
3. Persist:

```bash
$CHAPTER_PLAN_CTL write-themes \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --themes-file "<path to themes JSON>"
```

**Done (4.A):** `_lens-themes.json` validates; one entry per covered lens **and** every `presence=required` lens (zero-fact → `theme`/`desc` = `（待补）…`); unique `FL-*`. `write-themes --profile` enforces present∪required ⊆ `lens_keys`.

#### 4.B — Themes → chapter framework (once, after 4.A)

**Input (shared):** full `lens_themes[]`; optional outline `candidates`/`rules` as heuristics only — **do not** force isomorphism. Section-registry `heading`/`aliases` from Step 1.

##### 4.B-1 — Cluster (topology only)

- **Signal:** `desc` = primary clustering; `theme` = H3 seed only.
- **Produce** ordered chapter drafts: `id`, `anchor_form_lens_ids` (**array order = write/read order**), `sections[]` same order with `heading` **≡** corresponding `theme`.
- **Do not** set final `display_title` here. Chapter `lens_keys` = `anchor_form_lens_ids` ⨝ themes — **4.B-2 only reads them**.

##### 4.B-2 — Name `display_title`

For each chapter from 4.B-1:

1. **Get** `lens_keys` from that chapter's `anchor_form_lens_ids` via `_lens-themes`.
2. **Get** `material` = ordered `heading` + `aliases` from Step 1 section-registry for each key (anchor order; heading first per lens).
3. **Generate** `display_title` from `material` only — not from `desc`, `theme`, or facts. Use the chapter's full material (not one lens alone). Language of `display_title` must match that of the chapter's `theme`s.

- **Persist** (after 4.B-1 + 4.B-2; script does not invent titles):

```bash
$CHAPTER_PLAN_CTL write-framework \
  --revision-dir "$REVISION_DIR" \
  --framework-file "<path to framework JSON>"
```

**Done (4.B):** every theme `FL-*` in exactly one chapter; every `display_title` non-empty and from that chapter's registry `heading`/`aliases` only.

#### 4.C — Materialize placement (C1 mechanical → C2 multi-lens AI → C3 write)

1. **C1 (script):** Run propose — single-lens facts become `mechanical` rows; multi-lens go to `needs_resolution`:

```bash
$CHAPTER_PLAN_CTL propose-placement --revision-dir "$REVISION_DIR"
```

2. **C2 (AI):** For each `needs_resolution[]` entry, pick one `form_lens_id` from `candidates` using theme+desc; never expand outside `lens_tags`. Merge into the propose stdout `placement` draft:
   - Append `{fid, form_lens_id, placement: "ai_resolved", candidates}` under the chapter that owns that FL (`framework` / `fl→chapter`).
   - If that chapter id is **absent** from the draft `chapters[]` (all its facts were multi-lens), **create** the chapter object first.
   - `unmapped_facts` → return to **4.A/4.B** (missing theme or FL not in framework); do not invent tags.
3. **C3:** Persist placement SoT (use `--write` on propose only when `needs_resolution` and `unmapped_facts` are empty; otherwise `write-placement`):

```bash
$CHAPTER_PLAN_CTL write-placement \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --placement-file "<path to placement JSON>"
```

```bash
$CHAPTER_PLAN_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

**Done (Step 4):** `_lens-themes.json` + `_chapter-framework.json` + `_chapter-placement.json`; every fact with non-empty `lens_tags` placed exactly once; no `_chapters.json`.

### Step 5 — Write-by-FL then Assemble chapters

Keep chapter delivery shell (`_derive-{cid}.json`, `_body-{cid}.txt`, `append-chapter`). **Drop** Group / Arrange-as-axis / mixed-chapter Weave. Restore per-FL Write spine (I2b→I2c→I2d).

Artifacts per chapter:

```text
_derive-{cid}.json   # display_title (copy framework) + lens_forms[] per FL in chapter
_body-{cid}.txt      # ## omitted; H3 theme sections assembled in framework order
```

#### 5.W — Write-by-FL

For each `FL-x` (global or per-chapter `anchor_form_lens_ids` order):

1. Resolve `lens_key`, `theme` from `_lens-themes.json`.
2. `facts_ℓ` = facts in `_chapter-placement.json` with that `form_lens_id` (authoritative). Optional: `filter --lens` then **intersect** placement — never expand beyond placement.
3. **Derive F** then **Derive C** (S1): `carrier`/`structure` from `section-form-registry[lens_key].presentation.allowed`; `c[]` length 2..5. **Do not Write until F and C Done for this FL.**
4. **Write `lens_body`:** Scaffold per F; obey every C; content ⊆ `facts_ℓ`; carry anchors (L6); resolve raw `F-id` citations before persist; mark gaps with `> **待决：** …`. `lens_body` must not contain `### {theme}` (v1: in-memory / chapter buffer — no required `_body-lens-*` file).

**Note:** Encourage sectioning in the body. If using heading levels for structure, headings may start at `####`.

#### 5.A — Assemble-by-chapter then Close

Render order = `$CHAPTER_PLAN_CTL list-chapters` (`chapter_ids`: framework ∩ placement **with facts**).

**Skip** framework chapters that are **absent** from placement or have zero facts (do not write `_derive`/`_body`, do not `append-chapter`). Legal SoT omits unused chapters from placement — do **not** write `facts: []` (schema/L4 reject).

For each remaining `cid` in `list-chapters` order:

1. `display_title` ← **copy** framework (do not invent at write time).
2. Assemble body = optional one-sentence lead (no new facts) + each FL block in `anchor_form_lens_ids` order (`### {theme}` + `lens_body`).
3. Write `_derive-{cid}.json` (`display_title` + `lens_forms` for every FL in the chapter) and `_body-{cid}.txt`.
4. Close:

```bash
$COMPOSE_DOC_CONTROL append-chapter \
  --path "$OUTPUT_DOC_PATH" \
  --chapter-id "{cid}" \
  --revision-dir "$REVISION_DIR"
```

**Hard gate:** any FL missing F/C/body → do not assemble chapters that include it.

**Done:** every listed chapter (framework ∩ placement with facts) has `<!-- chapter:{cid} -->` and non-empty rendered content. Flat `## {display_title}` from `_derive-{cid}.json`.

### Step 6 — Validate

1. Run `$INIT_COMPOSE_VALIDATE` (placement SoT gates L1/L3/L4/C1 + chapter-artifact existence + assembly completeness + L6; rejects retired `_chapters.json`).
2. On failure → read stderr; **match the first prefix in this order** (then re-run Step 6):

| Order | Prefix / signal | Return to | Action |
|------:|-----------------|-----------|--------|
| 1 | `retired:` | delete file | Remove `_chapters.json`; do not edit themes/framework/placement for this signal |
| 2 | `L6:` | **5.W** | Write missing fact-anchor token into that FL body (do not weaken) |
| 3 | `L1:` / `L3:` / `L4:` | **4.C** | Fix placement; `write-placement` |
| 4 | `C1:` + derivation lens | Step 2–3 full re-run | inductive: **Blocking** → inductive-runner then Init 2 Branch A; deductive: re-run Step 2 then 3 — never patch in place; never `$INDUCTIVE_FACTS_PROJ project` |
| 5 | `C1:` true coverage gap (no derivation edge) | Round / modeling | Step 3 will not invent |
| 6 | `4.A:` | **4.A** | Re-induct themes; `write-themes` |
| 7 | `4.B:` | **4.B** | Fix framework; `write-framework` |
| 8 | `4.C:` | **4.C** | Fix placement; `write-placement` |
| 9 | `5.A:` | **5.A** | Re-assemble / `append-chapter` for `list-chapters` only |

Do **not** match bare `anchor` / `display_title` / `empty chapter` — use the prefixes above.

3. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Initializing complete (fact-first display layer).
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Facts: <REVISION_DIR>/_facts.json (<N> facts; Step 3 derived: <N>)
  Step 3: covered <M> required derivation lens(es); true gaps flagged: <ids or none>
  Chapter plan: <REVISION_DIR>/_lens-themes.json, _chapter-framework.json, _chapter-placement.json (<N> chapters)
  Chapter artifacts: <REVISION_DIR>/_derive-*.json, _body-*.txt
  Quarantined facts (empty lens_tags, Q1 audit): <N> — <ids or none>
  Scope cross-check: <SCOPE_REF_PATH>
  Draft status: Initialized
  Next step: parent pause gate (options from profile drafting.post_init_options)
```
