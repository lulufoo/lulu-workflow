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

**Pipeline:** Step 1 Load → Step 2 Validate facts → Step 3 Dynamic chapter plan → Step 4 Write-by-FL then Assemble → Step 5 Validate → Return.

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
| `$SCOPE_FACTS_PATH` | Upstream fact package path when registered; empty if none (Init does not Import) |
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

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-chapter`.

`$FACTS_CTL` subcommands: `--help` · `write` · `filter` · `validate` · `status`.

`$CHAPTER_PLAN_CTL` subcommands: `--help` · `write-themes` · `write-framework` · `propose-placement` · `write-placement` · `list-chapters` · `validate`.

> **K4:** `$INDUCTIVE_FACTS_PROJ project` is **retired**. Do not invoke projection from this runner.

## Execution Contract

### Step 1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE --role section-registry` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `aliases` / `intent` (else `desc`) / `intent_boundary` / `relations` / `presence` (used at Step 3)
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

`section_order` means the profile's *lens* set (same registry, reframed as intent lenses — see [Theory](../references/compose-theory.md)).

**Precondition:** Step 3 must produce `_lens-themes.json` + `_chapter-framework.json` + `_chapter-placement.json`. **`_chapters.json` is retired** — must not exist under `$REVISION_DIR`.

**Must:** place every fact with non-empty `lens_tags` exactly once in `_chapter-placement.json`; before persisting `_body-{cid}.txt`, resolve every author-time `F-id` citation into a human-readable chapter reference (write-side — `$INIT_COMPOSE_VALIDATE` does **not** scan for raw `F-id`); run `$INIT_COMPOSE_VALIDATE` before Return.
**Must not:** write a `fact:` or `section-key:` anchor into `$OUTPUT_DOC_PATH` (chapter anchors only); create or keep `_chapters.json`; decide open choices during Steps 2–3 (待决 same discipline); Import / Atomize / Derive facts.

### Step 2 — Validate facts

Producer (inductive or deductive) already wrote `_facts.json`. **Do not** atomize `$SCOPE_REF_PATH`, Import `$SCOPE_FACTS_PATH`, or Derive. Only validate:

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Missing / invalid `_facts.json` → Blocking (return to parent Drafting Step 0 producer; never re-atomize from scope).

**Structure/fact topology changes:** new revision + re-run Drafting Step 0 (producer) then Init — do not patch `lens_tags` / derivation in place here.

**Done:** validate exit 0 → proceed to Step 3.

### Step 3 — Dynamic chapter plan (themes → framework → placement)

**Must not:** dump full `_facts.json` into one model pass to invent themes; invent topology without 3.A→3.B→3.C; create `_chapters.json` (retired).

#### 3.A — Lens → theme + desc (SKILL loop; script filter)

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

**Done (3.A):** `_lens-themes.json` validates; one entry per covered lens **and** every `presence=required` lens (zero-fact → `theme`/`desc` = `（待补）…`); unique `FL-*`. `write-themes --profile` enforces present∪required ⊆ `lens_keys`.

#### 3.B — Themes → chapter framework (once, after 3.A)

**Input (shared):** full `lens_themes[]` only (cluster from `desc` / H3 from `theme`). Section-registry `heading`/`aliases` from Step 1.

##### 3.B-1 — Cluster (topology only)

- **Signal priority:**
  1. **Registry `cluster` (hard):** lenses sharing the same non-empty `cluster` slug **must** share one chapter; that chapter is **closed** (do not absorb lenses with a different `cluster` or with no `cluster`). Distinct `cluster` values never merge.
  2. **`desc` (soft):** primary clustering for lenses with no `cluster`.
- **`theme`** = H3 seed only (not a co-location signal).
- **Produce** ordered chapter drafts: `id`, `anchor_form_lens_ids` (**array order = write/read order**), `sections[]` same order with `heading` **≡** corresponding `theme`.
- **Do not** set final `display_title` here. Chapter `lens_keys` = `anchor_form_lens_ids` ⨝ themes — **3.B-2 only reads them**.

##### 3.B-2 — Name `display_title`

For each chapter from 3.B-1:

1. **Get** `lens_keys` from that chapter's `anchor_form_lens_ids` via `_lens-themes`.
2. **If** every key in that chapter shares the same non-empty registry `cluster`: **Generate** `display_title` from that `cluster` slug only (humanize the slug into a readable title). Do **not** use member `heading`/`aliases` as primary material. Language must match that of the chapter's `theme`s.
3. **Else:** **Get** `material` = ordered `heading` + `aliases` from Step 1 section-registry for each key (anchor order; heading first per lens). **Generate** `display_title` from `material` only — not from `desc`, `theme`, or facts. Use the chapter's full material (not one lens alone). Language of `display_title` must match that of the chapter's `theme`s.

- **Persist** (after 3.B-1 + 3.B-2; script does not invent titles):

```bash
$CHAPTER_PLAN_CTL write-framework \
  --revision-dir "$REVISION_DIR" \
  --framework-file "<path to framework JSON>"
```

**Done (3.B):** every theme `FL-*` in exactly one chapter; every `display_title` non-empty; same-`cluster` lenses co-located and closed; cluster-chapter titles derived from `cluster` (others from `heading`/`aliases` only).

#### 3.C — Materialize placement (C1 mechanical → C2 multi-lens AI → C3 write)

1. **C1 (script):** Run propose — single-lens facts become `mechanical` rows; multi-lens go to `needs_resolution`:

```bash
$CHAPTER_PLAN_CTL propose-placement --revision-dir "$REVISION_DIR"
```

2. **C2 (AI):** For each `needs_resolution[]` entry, pick one `form_lens_id` from `candidates` using theme+desc; never expand outside `lens_tags`. Merge into the propose stdout `placement` draft:
   - Append `{fid, form_lens_id, placement: "ai_resolved", candidates}` under the chapter that owns that FL (`framework` / `fl→chapter`).
   - If that chapter id is **absent** from the draft `chapters[]` (all its facts were multi-lens), **create** the chapter object first.
   - `unmapped_facts` → return to **3.A/3.B** (missing theme or FL not in framework); do not invent tags.
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

**Done (Step 3):** `_lens-themes.json` + `_chapter-framework.json` + `_chapter-placement.json`; every fact with non-empty `lens_tags` placed exactly once; no `_chapters.json`.

### Step 4 — Write-by-FL then Assemble chapters

Keep chapter delivery shell (`_derive-{cid}.json`, `_body-{cid}.txt`, `append-chapter`). **Drop** Group / Arrange-as-axis / mixed-chapter Weave. Restore per-FL Write spine (I2b→I2c→I2d).

Artifacts per chapter:

```text
_derive-{cid}.json   # display_title (copy framework) + lens_forms[] per FL in chapter
_body-{cid}.txt      # ## omitted; H3 theme sections assembled in framework order
```

#### 4.W — Write-by-FL

For each `FL-x` (global or per-chapter `anchor_form_lens_ids` order):

1. Resolve `lens_key`, `theme` from `_lens-themes.json`.
2. `facts_ℓ` = facts in `_chapter-placement.json` with that `form_lens_id` (authoritative). Optional: `filter --lens` then **intersect** placement — never expand beyond placement.
3. **Derive F** then **Derive C** (S1): `carrier`/`structure` from `section-form-registry[lens_key].presentation.allowed`; `c[]` length 2..5. **Do not Write until F and C Done for this FL.**
4. **Write `lens_body`:** Scaffold per F; obey every C; content ⊆ `facts_ℓ`; carry anchors (L6); resolve raw `F-id` citations before persist; mark gaps with `> **待决：** …`. `lens_body` must not contain `### {theme}` (v1: in-memory / chapter buffer — no required `_body-lens-*` file).

**Note:** Encourage sectioning in the body. If using heading levels for structure, headings may start at `####`.

#### 4.A — Assemble-by-chapter then Close

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

### Step 5 — Validate

1. Run `$INIT_COMPOSE_VALIDATE` (placement SoT gates L1/L3/L4/C1 + chapter-artifact existence + assembly completeness + L6; rejects retired `_chapters.json`).
2. On failure → read stderr; **match the first prefix in this order** (then re-run Step 5):

| Order | Prefix / signal | Return to | Action |
|------:|-----------------|-----------|--------|
| 1 | `retired:` | delete file | Remove `_chapters.json`; do not edit themes/framework/placement for this signal |
| 2 | `L6:` | **4.W** | Write missing fact-anchor token into that FL body (do not weaken) |
| 3 | `L1:` / `L3:` / `L4:` | **3.C** | Fix placement; `write-placement` |
| 4 | `C1:` + derivation / coverage | **Blocking** | Return to parent Drafting Step 0 producer (inductive or deductive); re-enter Init at Step 2 after producer rewrite — never patch facts in place; never `$INDUCTIVE_FACTS_PROJ project` |
| 5 | `4.A:` | **3.A** | Re-induct themes; `write-themes` (prefix is validator id, not Init step id) |
| 6 | `4.B:` | **3.B** | Fix framework; `write-framework` |
| 7 | `4.C:` | **3.C** | Fix placement; `write-placement` |
| 8 | `5.A:` | **4.A** | Re-assemble / `append-chapter` for `list-chapters` only |

Do **not** match bare `anchor` / `display_title` / `empty chapter` — use the prefixes above.

3. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Initializing complete (fact-first display layer).
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Facts: <REVISION_DIR>/_facts.json (<N> facts; producer-written, validate-only)
  Chapter plan: <REVISION_DIR>/_lens-themes.json, _chapter-framework.json, _chapter-placement.json (<N> chapters)
  Chapter artifacts: <REVISION_DIR>/_derive-*.json, _body-*.txt
  Quarantined facts (empty lens_tags, Q1 audit): <N> — <ids or none>
  Scope cross-check: <SCOPE_REF_PATH>
  Draft status: Initialized
  Next step: parent pause gate (options from profile drafting.post_init_options)
```
