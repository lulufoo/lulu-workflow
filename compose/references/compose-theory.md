# Compose Theory

> Ontological overview — substance, lens, presentation. Shared by compose producers and Writing; not a runner procedure.

## Profile & templates

Each compose stage has a `compose-profile.json` that selects framework templates (`section-registry`, `section-form-registry`, `section-kw-criteria`, `role-instance`, `domain-instance`).

| Template | Role |
|----------|------|
| `section-registry` | Intent SSOT: `intent`, boundary, upstream graph, `section_order`; optional per-lens `facets` string seeds |
| `section-form-registry` | Per-intent writing cognition (What): `reading_axis`, `presentation` (`guidance`, `allowed`+`when`, `forbidden`), `expression` |
| `section-kw-criteria` | Per-intent completeness altitude: KW rows only |
| `role-instance` | Stage author lens → expressive tendency (input to Write attention) |
| `domain-instance` | Stage domain lens → conventions (input to Write attention) |

**Axes:** registry = *what belongs* (belonging + optional facet seeds) · kw-criteria = *how deep* (altitude) · `section-form-registry` = *writing cognition* (What) · dynamic narrative arc = *where chapters sit*.

**Naming:** **writing cognition** = per-lens `{reading_axis, presentation, expression}` from `section-form-registry`. **F** = presentation carrier/structure choice under `presentation.allowed`.

## Ontology (three layers)

The theory below is governed by three ontological layers — substance, lens, and presentation — not one flat plane. A fact is **substance only**; everything about how it appears is rebuilt per consuming lens, never stored on the fact.

| Layer | Contains | Answers | Where it lives |
|-------|----------|---------|----------------|
| Substance (§1) | Content (facts) + anchors (§1.5) | what is true (stage-local) | `_facts.json` — producer-written (inductive discovery / deductive materialize + Derive); Writing validate-only (origins §1.2) |
| Lens / envelope (§2) | lens / intent / optional facet seeds (§2.4) | whose viewpoint owns it (N:M); seed reminders for detect | `lens_tags` + section-registry `intent` + optional `facets` string[] |
| Presentation (§3) | Writing cognition (What) + Assemble (arc titles / chapter anchors) | which reading / presentation / expression constraints apply under this lens; how the doc is labeled | per-lens `section-form-registry`; titles from `_narrative-arc` + `assemble-arc` |

**Invariant — substance carries no presentation.** One fact may be tagged to several lenses and is rebuilt differently under each. Writing cognition is not an attribute of the fact. Lens membership is *stored* (`lens_tags`); presentation is *applied on Write*, never persisted onto the fact.

**Stage-local substance vs delivery.** Within a revision, `_facts.json` is the substance read source for producers and presentation. Cross-stage delivery authority is the delivered document (`.md`); `_facts.json` is a process artifact and is **not** a cross-stage facts package.

## 1. Substance

### 1.1 Facts — definition

**Facts** — filtered substance in `_facts.json`. Producers write them; Writing validates only (no Atomize/Derive). The upstream scope document is intake material, not a second fact store.

Facts stay at decision-level substance (goals, boundaries, exclusions, decisions, invariants, phases). Presentation must not invent beyond facts / grounded code, nor restate another chapter's propositions.

### 1.2 Fact origins

Every fact has exactly one `origin.type`:

| origin | born when | provenance |
|--------|-----------|------------|
| `seed` | declared directly into the fact set (no open) | scope path + excerpt |
| `discovered` | a matured open expands 1:N into facts | open id |
| `derived` | deductive Derive after materialize | upstream fact ids |

Writing does not rewrite inductive SoT (validate-only — §1.1).

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
Atomize(scope document) → Atomize Eval → Derive → _facts.json
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

Membership is stored; presentation is applied per lens — the two must not be conflated.

### 2.2 Membership: `lens_tags`

`lens_tags` (on each fact) — N:M membership: one fact may belong to several lenses, each rebuilt under that lens's writing cognition. `lens_tags` are written at fact birth; `⊕=` never overwrites another lens in place. `Expose`'s `¬Settled` predicate (defined §1.3) tests exactly this `lens_tags` coverage.

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
- **Presentation:** seeds are not a writing-cognition axis; Write ignores them by default.

## 3. Presentation

Presentation applies **writing cognition (What)** from `section-form-registry` (disclosed per chapter via `$CHAPTER_WRITE_STATE begin.writing_cognition`), not a forced Derive→Scaffold procedure (How). Write uses that cognition and produces one chapter body. Choosing among `allowed` carriers (F as carrier/structure) is execution attention, not a machine-gated subprocess.

### 3.1 Reading axis

`reading_axis` (per lens, required key) — the abstract narrative axis for how this chapter should be read (not a content outline). Schema requires the key; a temporary empty string is allowed until the axis text is filled.

### 3.2 Presentation mechanisms (`presentation`)

Per lens, `presentation` carries:

- `guidance` — natural-language reminder of the lens's presentation intent
- `allowed[]` — optional carriers; each entry has `carrier`, `structure`, and `when` (under which condition that option applies)
- `forbidden` — carriers/structures explicitly excluded for this lens

These are **mechanisms** (What constraints), not enum-locked steps. Selection among `allowed` follows `when` and facts; Writing does not require persisting a chosen carrier/structure (F) artifact.

### 3.3 Expression mechanisms (`expression`)

`expression` states manner-of-expression constraints for the lens (`required` / `forbidden` string lists). It is cognitive input to Write — not a mandatory per-chapter Derive C array, and not content-substance rules.

Domain `expression_conventions` and Role Instance fields remain soft Write-time attention (register / carriers / scannability / altitude) when present.

### 3.4 Write unit & binding

**Write unit:** one chapter ticket = one `lens` + its placed facts → one `_body-{cid}.txt`.

**Binding:** before Write, load that lens's writing cognition (`reading_axis` + `presentation` + `expression`). Content ⊆ ticket facts; anchors must appear in the body; gaps → honest `待决`.

**Placement:** each fact → one chapter × lens (narrative arc is the topology). Outline `candidates` are optional heuristics only — not authoritative for placement.

### 3.5 Render: arc titles and chapter anchors

```text
visible titles = narrative-arc group/leaf via assemble-arc
chapter body   = <!-- chapter:{cid} --> + _body-{cid}.txt
```

Lens chapter headings are omitted by default (`--lens-heading omit`). Locate chapters by anchor, not H2 text.

## Synthesis pipeline

> Cross-cutting (not a fourth layer): producers first, then Writing presentation.

Substance (§1) is produced by **Induce** or **Deduce** (§1.3–1.4), then dispatched through lenses (§2) and written per presentation (§3):

```text
# per chapter ticket (one lens)
lens_body = Write( facts_ℓ ; writing_cognition_ℓ )
  — facts_ℓ from chapter ticket; cognition = reading_axis + presentation + expression
  — persist _body-{cid}.txt

# document (thin assemble — not a second creative write)
doc = Assemble-arc(
  titles ← _narrative-arc,
  for each cid: chapter anchor + _body
)
```

**Producer then Writing:** Induce or Deduce (§1.3–1.4) completes before presentation. Writing does not Atomize or Derive facts.

**Intent text:** Use `sections.{key}.intent` when present; else `sections.{key}.desc` (legacy).

Display-layer quality gates: see [`writing-draft-quality.md`](writing-draft-quality.md).
