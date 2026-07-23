# Compose Theory

> Ontological overview — substance, lens, presentation. Shared by compose producers and Init; not a runner procedure.

## Profile & templates

Each compose stage has a `compose-profile.json` that selects framework templates (`section-registry`, `section-form-registry`, `section-kw-criteria`, `role-instance`, `domain-instance`).

| Template | Role |
|----------|------|
| `section-registry` | Intent SSOT: `intent`, boundary, upstream graph, `section_order`; optional per-lens `facets` string seeds |
| `section-form-registry` | Per-intent presentation/expression: `presentation` (`guidance`, `allowed`, `forbidden`), `expression` (optional) |
| `section-kw-criteria` | Per-intent completeness altitude: KW rows only |
| `role-instance` | Stage author lens → F/C |
| `domain-instance` | Stage domain lens → F/C |

**Axes:** registry = *what* (belonging + optional facet seeds) · kw-criteria = *how deep* (altitude) · form / role / domain = *how to write* · dynamic chapter plan = *where*.

## Ontology (three layers)

The theory below is governed by three ontological layers — substance, lens, and presentation — not one flat plane. A fact is **substance only**; everything about how it appears is rebuilt per consuming lens, never stored on the fact.

| Layer | Contains | Answers | Where it lives |
|-------|----------|---------|----------------|
| Substance (§1) | Content (facts) + anchors (§1.5) | what is true (stage-local) | `_facts.json` — producer-written (inductive discovery / deductive materialize + Derive); Init validate-only (origins §1.2) |
| Lens / envelope (§2) | lens / intent / optional facet seeds (§2.4) | whose viewpoint owns it (N:M); seed reminders for detect | `lens_tags` + section-registry `intent` + optional `facets` string[] |
| Presentation (§3) | Form (`F`) + Expression (`C`) + Render (`display_title` / H3 theme) | how to carry / write (per `form_lens`) + how to label | F/C per `form_lens`; `display_title` and H3 themes from the chapter plan |

**Invariant — substance carries no presentation.** One fact may be tagged to several lenses and is rebuilt differently under each. Form and Expression are not attributes of the fact. Lens membership is *stored* (`lens_tags`); presentation is *derived on demand*, never persisted onto the fact.

**Stage-local substance vs delivery.** Within a revision, `_facts.json` is the substance read source for producers and presentation. Cross-stage delivery authority is the delivered document (`.md`); `_facts.json` is a process artifact and is **not** a cross-stage facts package.

## 1. Substance

### 1.1 Facts — definition

**Facts** — filtered substance in `_facts.json`. Producers write them; Init validates only (no Atomize/Derive). The upstream scope document is intake material, not a second fact store.

Facts stay at decision-level substance (goals, boundaries, exclusions, decisions, invariants, phases). Presentation must not invent beyond facts / grounded code, nor restate another chapter's propositions.

### 1.2 Fact origins

Every fact has exactly one `origin.type`:

| origin | born when | provenance |
|--------|-----------|------------|
| `seed` | declared directly into the fact set (no open) | scope path + excerpt |
| `discovered` | a matured open expands 1:N into facts | open id |
| `derived` | deductive Derive after materialize | upstream fact ids |

Init does not rewrite inductive SoT (validate-only — §1.1).

### 1.3 Inductive generation (`Induce`)

`Induce` is inductive (unknown substance → discover, ground, decide, fold): the inductive-runner writes `_facts.json` directly (K4; no projection) and tracks opens in `inductive-opens.json`. `Write` (§3) only weaves already-produced facts into prose — it does **not** produce facts.

```text
_facts.json  ⊕=  Expand( open_point )   # via settle → 1:N facts
open_point = Expose(trigger × means)  # kept iff ( frontier_KW row false  ∧  ¬Settled )
```

- `Expand` — ground → propose → **user decides** → settle / defer / reject into the fact set.
- `⊕=` — append with `lens_tags`; deepen by KW; never overwrite another lens in place.
- Seed is not Expose: it writes `origin.type=seed` facts directly (no open).

`Expose` finds open points as **trigger × means** (ai or human), gated by `frontier_kw`, minus `¬Settled` (`lens_tags` coverage). Means names and probes live in the inductive runner.

### 1.4 Deductive materialization (`Deduce`)

`Deduce` materializes known upstream into this stage's addressable facts (whole→parts) and writes `_facts.json`. `Write` as in §1.3.

```text
Atomize(scope document) → fidelity → Derive → _facts.json
```

- **Atomize** — facts from the upstream scope document, tagged with this stage's `lens_tags`.
- **Fidelity** — doc↔facts must clear before Derive.
- **Derive** — Intent ceiling + edge floor; gaps → human confirm (not silent invention).

### 1.5 Fact anchors (born-with identity)

**Anchors** are a fact's machine-relevant evidence tokens — the paths, artifacts, symbols, APIs, and code refs a fact commits to. They live as an optional `anchors[]` field on the fact (`{kind, value}`). Anchors are **substance, not presentation**: they are lens-invariant (the same path reads the same under any lens) and say *what is true*, never *how it is shown*. They belong to substance (§1), not presentation (§3).

Anchors are set at fact birth (one write, no later mutation): declared on seed/discovered, or inherited on derived from `source` facts.

**Invariant — anchors must survive into the body.** A placed fact's anchors appear in that chapter's body.

**After settlement.** The fact holds the evidence; `code_refs` on a settled open are provenance only. Downstream reads `_facts.json`, not opens. Cross-stage delivery SSOT remains the document (see Ontology).

**Authoring convention.** In fact `text`, wrapping machine-relevant tokens in backticks is an optional readability hint for humans; it is **not** a data contract — anchors come from declared or inherited `anchors[]`, never from parsing prose.

## 2. Lens (envelope)

### 2.1 Lens — definition

A lens is a **viewpoint that owns a subset of substance**. It is the classification gate that runs *before* presentation: it decides which facts belong, not how they are shown. A lens is neither a container nor a writing style — it is the "whose is this" partition.

- `intent` / `intent_boundary` (section-registry) — the lens's inclusion charter and its exclusion list. `intent_boundary` names substance belonging to *other* lenses; author none of it here.

Membership is stored; presentation is derived per lens — the two must not be conflated.

### 2.2 Membership: `lens_tags`

`lens_tags` (on each fact) — N:M membership: one fact may belong to several lenses, each rebuilding it under its own F/C. `lens_tags` are written at fact birth; `⊕=` never overwrites another lens in place. `Expose`'s `¬Settled` predicate (defined §1.3) tests exactly this `lens_tags` coverage.

### 2.3 Lens maturity: `frontier_kw`

`frontier_kw` (inductive maturity ledger) — per-lens completeness altitude. Inductive generation (§1.3) reads it via `Expose` to decide whether a lens still needs facts (the `kept iff` predicate lives in §1.3).

### 2.4 Facet seeds

Optional **facet seeds** are short string labels on a section-registry lens (`facets: string[]`, roughly 3–5 English words each). They are **inductive detect reminders**.

```text
breadth: lens ∈ coverage_sections
depth:   frontier_kw              # altitude, per-lens only
seeds:   facets string[]          # optional; prompt input only
```

- **Declaration:** optional `facets` string array on a section entry. No list ⇒ no seed reminder for that lens.
- **Use:** optional non-exhaustive detect reminders — not a completeness gate, not open/fact identity, not a closed question space.
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
- `c` — the criterion for that dimension, derived from role fields, domain instance, intent, that lens's `presentation`, that lens's `expression`, or `expression_conventions`

`expression_conventions` may include grounding clauses (e.g. cite paths only when verified elsewhere). They do not add facts.

C has 2–5 pairs per `form_lens`. Every `c` must be traceable to role fields, `expression_conventions`, lens `presentation`, lens `expression`, or intent; no pair is invented without grounding in these sources.

### 3.3 F/C priority & binding

**Binding:** F/C per `form_lens` before Write. **F priority:** lens `presentation` > domain conventions > role tendency > intent. **Placement:** each fact → one chapter × `form_lens` (chapter plan is the topology). Outline `candidates` are optional heuristics only — not authoritative for placement.

### 3.4 Render: `display_title` and H3 themes

```text
display_title = framework title   # H2
H3 = theme per form_lens block inside the chapter body
```

### 3.5 Document assembly

**Assembly:** chapter anchor `<!-- chapter:{cid} -->`, then `## {display_title}`, then H3 body blocks in plan order. Locate chapters by anchor, not H2 text.

## Synthesis pipeline

> Cross-cutting (not a fourth layer): how the layers relate in the pipeline — producers first, then Init presentation.

Substance (§1) is produced by **Induce** or **Deduce** (§1.3–1.4), then dispatched through lenses (§2) and rendered per presentation (§3):

```text
# per form_lens / FL-x (presentation)
lens_body = Write( facts_ℓ ; F_ℓ, C_ℓ )
  — facts_ℓ from chapter placement; Scaffold per F; obey every C

# per chapter (thin assemble — not a second creative write)
chapter_body = Assemble(
  H2 ← framework display_title,
  for FL in chapter form_lens order:
    H3 ← themes[FL].theme,
    lens_body[FL]
)
```

**Producer then Init:** Induce or Deduce (§1.3–1.4) completes before presentation. Init does not Atomize or Derive.

**Intent text:** Use `sections.{key}.intent` when present; else `sections.{key}.desc` (legacy).

Display-layer quality gates: see [`init-draft-quality.md`](init-draft-quality.md).
