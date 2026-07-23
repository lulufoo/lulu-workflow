# Compose Theory

> Ontological overview — substance, lens, presentation. Shared by compose producers and Init; not a runner procedure.

## Profile SSOT

Compose stage configuration lives at `{WORKFLOW_ROOT}/{stage}/compose-profile.json` (not under `compose/profiles/`). After `start`, runtime resolves the same file via session cache pointer `.compose-profile-path` under `{cache_subdir}/`.

## Framework templates

Scheme keys: `schemes/compose-template-scheme.json`. Each profile maps them via `compose-profile.json` → `framework_templates`.

| Template | Role |
|----------|------|
| `section-registry` | Intent SSOT: `intent`, boundary, upstream graph, `section_order`; optional per-lens `facets` string seeds |
| `section-form-registry` | Per-intent presentation/expression: `presentation` (`guidance`, `allowed`, `forbidden`), `expression` (optional) |
| `section-kw-criteria` | Per-intent completeness altitude: KW rows only |
| `role-instance` | Stage author lens → F/C |
| `domain-instance` | Stage domain lens → F/C |

**Axes:** registry = *what* (belonging + optional facet seeds) · kw-criteria = *how deep* (altitude) · form / role / domain = *how to write* · dynamic chapter plan (Init Step 3) = *where*.

## Ontology (three layers)

The theory below is governed by three ontological layers. A fact is **substance only**; everything about how it appears is rebuilt per consuming lens, never stored on the fact. Reading these as one flat plane is the modelling error the `section → fact + lens` refactor removed.

| Layer | Contains | Answers | Where it lives |
|-------|----------|---------|----------------|
| Substance (§1) | Content (facts) + anchors (§1.6) | what is true (stage-local) | `_facts.json` — producer-written (inductive discovery / deductive materialize+Derive); Init validate-only (origins §1.2) |
| Lens / envelope (§2) | lens / intent / optional facet seeds (§2.4) | whose viewpoint owns it (N:M); seed reminders for detect | `lens_tags` + section-registry `intent` + optional `facets` string[] |
| Presentation (§3) | Form (`F`) + Expression (`C`) + Render (`display_title` / H3 theme) | how to carry / write (per `form_lens`) + how to label | F/C at Init Step 4.W per FL; `display_title` copied from framework into `_derive-{cid}.json`; H3 from `_lens-themes.json` |

**Invariant — substance carries no presentation.** One fact may be tagged to several lenses and is rebuilt differently under each; therefore Form/Expression cannot be attributes of the fact. Lens membership is *stored* (`lens_tags`); presentation is *derived on demand*, never persisted onto the fact.

**Stage-local substance vs delivery.** Within a revision, `_facts.json` is the substance read source for producers and presentation. Cross-stage delivery authority is the delivered document (`.md`); `_facts.json` is a process artifact and is **not** a cross-stage facts package.

## 1. Substance

### 1.1 Facts — definition

**Facts** — filtered substance in `_facts.json`. Display-layer Init **validate-only** on producer-written facts (inductive discovery or deductive-runner; no K2 projection; no Init Atomize/Derive). Scope / upstream delivery doc is intake material and completeness cross-check, not a second fact store. Code grounding (when `drafting.code_grounding`) may add path/symbol detail at Write with `code_refs`.

- Covers goals, boundaries, exclusions, decisions, invariants, phases at the decision level.
- Rewrite as operational prose; not scope-doc verbatim paste (and not hand-rewriting inductive JSON — use section-control commands).
- Must not introduce capabilities, scope, or boundaries beyond inductive SoT / facts / grounded code.
- May leave a chapter as `（待补）` when coverage is intentionally open; do not invent filler.
- Must not restate propositions whose home chapter already carries them — cite by chapter reference instead.

### 1.2 Fact origins

Every fact in `_facts.json` is born through exactly one of three origins (`origin.type`; SSOT `facts_schema.py` `ORIGIN_TYPES`). There is one shared downstream — `facts_schema.save_facts` (validate + normalize) — not one entry point:

| origin | born at | provenance |
|--------|---------|------------|
| `seed` | `seed-decision` (Seed/G1) — writes `_facts.json` directly, no open | scope path + excerpt |
| `discovered` | `settle-open` (G3) — a matured open expands to 1:N facts | `origin.ref = [open_id]` |
| `derived` | deductive Derive — append contiguous derived facts after materialize | upstream `source` / origin.ref fact ids |

Init treats producer-written facts as read-only (validate-only) and never writes back into the inductive SoT.

### 1.3 How facts are born: Inductive generation (`Induce`)

`Induce` is inductive (unknown substance → discover, ground, decide, fold): the inductive-runner writes `_facts.json` directly (K4; no projection) and tracks opens in `inductive-opens.json`. `Write` (§3) only weaves already-produced facts into prose — it does **not** produce facts.

```text
_facts.json  ⊕=  Expand( open_point )   # via settle-open → 1:N facts
open_point = Expose(trigger × means)  # kept iff ( frontier_KW row false  ∧  ¬Settled )
```

- `Expand` = ground (`attach-code-refs` on `O-`) → AI leaning → **user decides** (auto/manual/ignore batch) ⇒ `settle-open` / `defer-open` / `reject-open`.
- `⊕=` = append facts with `lens_tags`; deepens by KW on maturity ledger; never overwrites another lens's facts in place.
- Handoff: discovery-written `_facts.json` → Init (validate-only on inductive).

`Expose` discovers open points via **trigger × means** (gated by each lens's `frontier_kw` maturity — defined in §2.3). All sources subtract `¬Settled` (facts whose `lens_tags` cover the lens) and land in `inductive-opens.json`:

| trigger | means | probe | gap predicate | frontier_KW |
|---------|-------|-------|---------------|:---:|
| ai | `ai_scan` | run `methods` over code | KW row false | applies |
| ai | `ai_intent_baseline` | demand manifest vs section | fulfillment false | applies |
| ai | `ai_scope_scan` | decision-fact units vs design lenses | unit unsettled / gap | applies |
| ai | `ai_probe` | 4 black-box lenses (failure/boundary/assumption/seam) | silence ∧ KW-false | applies |
| human | `human_probe` / `human_direct` / `human_view` | user question / assertion / view-found gap | user assertion | exempt |

Seed is **not** an Expose source: it writes `_facts.json` directly with `origin.type=seed` (hybrid `origin.ref`: scope path + excerpt; no open stamp).

### 1.4 How facts are born: Deductive materialization (`Deduce`)

`Deduce` is the dual of `Induce`: known upstream → this stage's addressable facts (whole→parts). It writes `_facts.json`; `Write` does not.

```text
Atomize(scope document) → fidelity → Derive → _facts.json
```

- **Atomize** — cut facts from the upstream **scope document**; tag `lens_tags` for this stage. Never Import upstream compose `_facts.json` (delivery SSOT = document; see Ontology).
- **Fidelity** — doc↔facts must clear before Derive.
- **Derive** — from this stage's facts under Intent (ceiling + edge floor); undecidable gaps → human confirm, not silent invention.

### 1.5 Codebase grounding

**Codebase grounding (profile flag):** Driven by `drafting.code_grounding` (boolean; orthogonal to `drafting.inductive`). When `true`: at Write, bind named symbols in facts / registry-required path fields to real artifacts under `$PROJECT_ROOT` (Grep/Glob/Read, bounded); success → body increment + derive `code_refs` as `path` or `path#symbol`; failure → no invented paths, body `待决`. When `false`: Init does not run this pass — code refs come from inductive `attach-code-refs` upstream if at all. Grounding never writes back into inductive SoT.

### 1.6 Fact anchors (born-with identity)

**Anchors** are a fact's machine-relevant evidence tokens — the paths, artifacts, symbols, APIs, and code refs a fact commits to. They live as an optional `anchors[]` field on the fact (`{kind, value}`; `kind ∈ ANCHOR_KINDS`, SSOT `facts_schema.py`). Anchors are **substance, not presentation**: they are lens-invariant (the same path reads the same under any lens) and say *what is true*, never *how it is shown*. This is why they sit on the fact (§1) and not in the presentation layer (§3) — they do not violate the "substance carries no presentation" invariant.

Anchors are acquired **at fact birth**, one write, no later mutation — declare-first, mechanical fallback:

| origin | how anchors are acquired |
|--------|--------------------------|
| `seed` | the creator declares `anchors` alongside `--text` (`seed-decision --anchors`) |
| `discovered` | each `settle-open --facts-file` entry may declare `anchors`; if omitted, the open's `code_refs` are distributed by path/symbol substring to the matching resolved facts (unmatched refs stay on the open) |
| `derived` | inherited mechanically — union of the `source` facts' anchors |

**Invariant — anchors must survive into the body.** A fact placed in a chapter carries its anchors into that chapter's rendered body; abstracting them away is a substance loss. Init's validation enforces this mechanically (the anchor-coverage check: every `discovered` fact's anchors must appear as a normalized substring in its chapter body; `code_ref` matches OR over its `path`/`symbol` segments).

**Stage-local SoT after settlement.** Once an open is settled, the fact is the live substance record for its evidence inside the revision; the `code_refs` remaining on the settled open are historical provenance only. Downstream (Init and later) reads `_facts.json`, not opens — a "transient upstream → durable substance" projection, not duplicate storage. This does **not** make `_facts.json` the cross-stage delivery SSOT (see Ontology).

**Authoring convention.** In fact `text`, wrapping machine-relevant tokens in backticks is an optional readability hint for humans; it is **not** a data contract — anchors come from the declared `anchors[]` (or the fallback), never from parsing prose.

## 2. Lens (envelope)

### 2.1 Lens — definition

A lens is a **viewpoint that owns a subset of substance**. It is the classification gate that runs *before* presentation: it decides which facts belong, not how they are shown. A lens is neither a container nor a writing style — it is the "whose is this" partition.

- `intent` / `intent_boundary` (section-registry) — the lens's inclusion charter and its exclusion list. `intent_boundary` names substance belonging to *other* lenses; author none of it here.

Membership is stored; presentation is derived per lens at Step 4.W — the two must not be conflated.

### 2.2 Membership: `lens_tags`

`lens_tags` (on each fact) — N:M membership: one fact may belong to several lenses, each rebuilding it under its own F/C. `settle-open` / `seed-decision` write them at fact birth; `⊕=` never overwrites another lens's facts in place. `Expose`'s `¬Settled` predicate (defined §1.3) tests exactly this `lens_tags` coverage.

### 2.3 Lens maturity: `frontier_kw`

`frontier_kw` (inductive maturity ledger) — per-lens completeness altitude. Inductive generation (§1.3) reads it via `Expose` to decide whether a lens still needs facts (the `kept iff` predicate lives in §1.3).

### 2.4 Facet seeds

Optional **facet seeds** are short string labels on a section-registry lens (`facets: string[]`, roughly 3–5 English words each). They are **inductive detect reminders**, not a completeness gate and not open/fact identity.

```text
breadth: lens ∈ coverage_sections
depth:   frontier_kw              # altitude, per-lens only
seeds:   facets string[]          # optional; prompt input only
```

- **Declaration:** optional `facets` string array on a section entry. No list ⇒ no seed reminder for that lens.
- **Use:** Class 1B detect pastes seeds into the prompt as a **non-exhaustive** set; demand + Context friction may open gaps outside the list. Design: `compose-inductive-facet-seeds-and-cmp-design.md`.
- **Not used for:** `clear-section`, `facet_id` fields, must/optional receipts, or closed question spaces.
- **Presentation:** seeds are not an F/C axis; Write ignores them by default.

## 3. Presentation

### 3.1 Form (F) — definition

F describes how a fact group's content is carried and organized for a given `form_lens`. It has three fields:

- `carrier` — the primary container type for the content (the main vehicle through which information is presented)
- `structure` — the internal organization of the carrier: layout, hierarchy, diagram type and its communicative purpose
- `forbidden` — forms explicitly excluded for this lens, derived from intent_boundary, section `guidance`, and derivation conflicts

All three fields are derived natural-language descriptions, not enum values. F is derived **per `form_lens`** (from `section-form-registry` for that lens), not once for the whole chapter. Its value depends on that lens's `presentation`/`guidance`, domain conventions, role expressive tendency, and intent — in that priority order when they conflict.

### 3.2 Expression (C) — definition

C is the set of writing constraints that govern how content is expressed inside F for a given `form_lens`. It is a collection of `(d, c)` pairs where:

- `d` — the writing dimension (e.g., granularity, vocabulary, abstraction level, tone, completeness bar)
- `c` — the criterion for that dimension, derived from `### Role Fields`, domain instance, intent, that lens's `presentation`, that lens's `expression.required`/`expression.forbidden`, or `expression_conventions`

`expression_conventions` may include grounding clauses (e.g. cite paths only when verified elsewhere); they govern **how** to write, not **what** Init injects into facts.

C has 2–5 pairs per `form_lens`. Every `c` must be traceable to a specific `### Role Fields` field, `expression_conventions`, lens `presentation`, lens `expression`, or intent clause; no pair is invented without grounding in these sources.

### 3.3 F/C priority & binding

**Derivation:** Read `### Role Fields` and `domain instance` for shared authoring constraints; bind F/C **per distinct `form_lens` / FL-x** (Step 4.W) before Write. No static dimension tables, vocabulary enums, or form lookup configs beyond `section-form-registry`.

**F priority (conflict resolution):** lens `presentation` (via `form_lens`) > domain `expression_conventions` > role `expressive_tendency` > intent text. `intent_boundary` is an exclusion list — it names substance belonging to other intents; author none of it here.

**Placement:** fact → chapter × FL-x is decided in Step 3 (`_chapter-placement.json`). Outline `candidates` are optional heuristics only — not the topology SSOT.

### 3.4 Render: `display_title` and H3 themes

```text
display_title = copy( framework.display_title )   # H2; SoT in _chapter-framework.json
  — persisted on _derive-{cid}.json for append-chapter; do not invent at Write time

H3 = themes[FL].theme   # per form_lens block inside the chapter body
```

### 3.5 Document assembly

**Document assembly:** Compose documents use chapter anchors — `<!-- chapter:{cid} -->`, then `## {display_title}`, then body (H3 theme sections in `anchor_form_lens_ids` order). Initializing persists each chapter via `$COMPOSE_DOC_CONTROL append-chapter`, which reads `_derive-{cid}.json` / `_body-{cid}.txt`. Downstream compose/eval tools locate chapters by chapter anchor, not H2 text. Section-key grammar retired (K3-d).

## Synthesis pipeline

> Cross-cutting (not a fourth layer): how the three layers combine — producers first, then Init presentation.

Substance (§1) is produced by **Induce** or **Deduce** (§1.3–1.4), then dispatched through lenses (§2) and rendered per presentation (§3):

```text
# per form_lens / FL-x (presentation)
lens_body = Write( facts_ℓ ; F_ℓ, C_ℓ )
  — facts_ℓ from _chapter-placement.json; Scaffold per F; obey every C

# per chapter (thin assemble — not a second creative write)
chapter_body = Assemble(
  H2 ← copy(framework.display_title),
  for FL in framework.anchor_form_lens_ids:
    H3 ← themes[FL].theme,
    lens_body[FL]
)
```

**Producer then Init:** Induce or Deduce (§1.3–1.4) completes before presentation. Init does not Atomize or Derive.

**Init order (strict):** Validate facts (Step 2) → Dynamic chapter plan (Step 3: themes → framework → placement SoT) → Write-by-FL then Assemble (Step 4: `_derive-{cid}.json` + `_body-{cid}.txt`) → `append-chapter` → Validate (Step 5 reads placement). `_chapters.json` retired.

**Intent text:** Use `sections.{key}.intent` when present; else `sections.{key}.desc` (legacy).

## Init draft quality floor

Initializing must operationalize fact substance into readable chapters; scope-external speculation remains prohibited. `$INIT_COMPOSE_VALIDATE` gates Init completion via display-layer checks only. Contract: [`init-draft-quality.md`](init-draft-quality.md).

## Constraints

**Prohibited:**

- scope-doc verbatim paste, `[Source: …]`, `decision-doc-mapping`
- facts / chapter prose that adds capabilities, scope, or boundaries not in scope / inductive SoT
- speculative paths, APIs, or behavior not grounded in scope / facts / inductive SoT / committed upstream decomposition, and not obtained via `drafting.code_grounding` (when enabled: ground or `待决` — never invent)
- `<!-- section-key:… -->` anchors or section-key Init artifact names (`_title-display.json`, `_partition.json`, `_derive-{section_key}.json`)
- verbatim `sections.{key}.heading` as chapter `display_title`
- treating stage `_facts.json` as cross-stage delivery SSOT, or Importing upstream compose `_facts.json` as a delivery package
