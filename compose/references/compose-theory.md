# Compose Theory

> Referenced by: initializing-runner (and any runner that generates chapter body content).

## Profile SSOT

Compose stage configuration lives at `{WORKFLOW_ROOT}/{stage}/compose-profile.json` (not under `compose/profiles/`). After `start`, runtime resolves the same file via session cache pointer `.compose-profile-path` under `{cache_subdir}/`.

## Framework templates

Scheme keys: `schemes/compose-template-scheme.json`. Each profile maps them via `compose-profile.json` → `framework_templates`.

| Template | Role |
|----------|------|
| `section-registry` | Intent SSOT: `intent`, boundary, upstream graph, `section_order` |
| `section-form-registry` | Per-intent presentation/expression: `presentation` (`guidance`, `allowed`, `forbidden`), `expression` (optional) |
| `section-kw-criteria` | Per-intent completeness dimensions |
| `role-instance` | Stage author lens → F/C |
| `domain-instance` | Stage domain lens → F/C |
| `outline-registry` | Block→intent document layout |

**Axes:** registry = *what* · kw-criteria = *how complete* · form / role / domain = *how to write* · outline = *where*.

## Ontology (three layers)

The theory below is governed by three ontological layers. A fact is **substance only**; everything about how it appears is rebuilt per consuming lens, never stored on the fact. Reading these as one flat plane is the modelling error the `section → fact + lens` refactor removed.

| Layer | Contains | Answers | Where it lives |
|-------|----------|---------|----------------|
| Substance (§1) | Content (facts) | what is true | `_facts.json` — inductive: discovery-written; deductive: atomized (origins §1.2) |
| Lens / envelope (§2) | lens / intent | whose viewpoint owns it (N:M) | `lens_tags` on each fact + section-registry `intent` |
| Presentation (§3) | Form (`F`) + Expression (`C`) + Render (`display_title`) | how to carry / write (per `form_lens`) + how to label (per chapter) | F/C at Step 5.2 Bind per `form_lens`; `display_title` in `_derive-{cid}.json`, rendered at `append-chapter` |

**Invariant — substance carries no presentation.** One fact may be tagged to several lenses and is rebuilt differently under each; therefore Form/Expression cannot be attributes of the fact. Lens membership is *stored* (`lens_tags`); presentation is *derived on demand*, never persisted onto the fact.

## 1. Substance

### 1.1 Facts — definition

**Facts** — filtered substance in `_facts.json`. Display-layer Init reads facts (inductive: discovery-written; no K2 projection). Scope doc is completeness cross-check only. Code grounding (when `drafting.code_grounding`) may add path/symbol detail at Write with `code_refs`.

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
| `derived` | Step 3 derive (`derive_shell.append_derived_facts`, contiguous `F-(k+1)..`) | upstream `source` fact ids |

Init treats inductive facts as read-only (validate-only) and never writes back into the inductive SoT.

### 1.3 How facts are born: Inductive generation (`Induce`)

`Write` is deductive (known substance → organized prose). `Induce` is inductive (unknown substance → discover, ground, decide, fold): the inductive-runner writes `_facts.json` directly (K4; no projection) and tracks opens in `inductive-opens.json`.

```text
_facts.json  ⊕=  Expand( open_point )   # via settle-open → 1:N facts
open_point = Expose(trigger × means)  # kept iff ( frontier_KW row false  ∧  ¬Settled )
```

- `Expand` = ground (`attach-code-refs` on `O-`) → AI leaning → **user decides** (auto/manual/ignore batch) ⇒ `settle-open` / `defer-open` / `reject-open`.
- `⊕=` = append facts with `lens_tags`; deepens by KW on maturity ledger; never overwrites another lens's facts in place.
- Handoff: discovery-written `_facts.json` → Init Steps 2–6 (validate-only on inductive).

`Expose` discovers open points via **trigger × means** (gated by each lens's `frontier_kw` maturity — defined in §2.3). All sources subtract `¬Settled` (facts whose `lens_tags` cover the lens) and land in `inductive-opens.json`:

| trigger | means | probe | gap predicate | frontier_KW |
|---------|-------|-------|---------------|:---:|
| ai | `ai_scan` | run `methods` over code | KW row false | applies |
| ai | `intent_baseline` | demand manifest vs section | fulfillment false | applies |
| ai | `probe` | 4 black-box lenses (failure/boundary/assumption/seam) | silence ∧ KW-false | applies |
| human | `probe` / `direct` / `view` | user question / assertion / view-found gap | user assertion | exempt |

Seed is **not** an Expose source: it writes `_facts.json` directly with `origin.type=seed` (hybrid `origin.ref`: scope path + excerpt; no open stamp).

### 1.4 Codebase grounding

**Codebase grounding (profile flag):** Driven by `drafting.code_grounding` (boolean; orthogonal to `drafting.inductive`). When `true`: at Write, bind named symbols in facts / registry-required path fields to real artifacts under `$PROJECT_ROOT` (Grep/Glob/Read, bounded); success → body increment + derive `code_refs` as `path` or `path#symbol`; failure → no invented paths, body `待决`. When `false`: Init does not run this pass — code refs come from inductive `attach-code-refs` upstream if at all. Grounding never writes back into inductive SoT.

## 2. Lens (envelope)

### 2.1 Lens — definition

A lens is a **viewpoint that owns a subset of substance**. It is the classification gate that runs *before* presentation: it decides which facts belong, not how they are shown. A lens is neither a container nor a writing style — it is the "whose is this" partition.

- `intent` / `intent_boundary` (section-registry) — the lens's inclusion charter and its exclusion list. `intent_boundary` names substance belonging to *other* lenses; author none of it here.

Membership is stored; presentation is derived per lens at Step 5.2 — the two must not be conflated.

### 2.2 Membership: `lens_tags`

`lens_tags` (on each fact) — N:M membership: one fact may belong to several lenses, each rebuilding it under its own F/C. `settle-open` / `seed-decision` write them at fact birth; `⊕=` never overwrites another lens's facts in place. `Expose`'s `¬Settled` predicate (defined §1.3) tests exactly this `lens_tags` coverage.

### 2.3 Lens maturity: `frontier_kw`

`frontier_kw` (inductive maturity ledger) — per-lens completeness altitude. Init's Inductive generation (§1.3) reads it via `Expose` to decide whether a lens still needs facts (the `kept iff` predicate lives in §1.3).

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

**Derivation:** Read `### Role Fields` and `domain instance` for shared authoring constraints; bind F/C **per distinct `form_lens`** in the chapter (Step 5.2 Bind). No static dimension tables, vocabulary enums, or form lookup configs beyond `section-form-registry`.

**F priority (conflict resolution):** lens `presentation` (via `form_lens`) > domain `expression_conventions` > role `expressive_tendency` > intent text. `intent_boundary` is an exclusion list — it names substance belonging to other intents; author none of it here.

**§7.4 placement heuristic (content-kind memo, not a lens total order):** invariants > structure/contract > success > contact > context — used by Step 4/Step 5 as AI reference only.

### 3.4 Render: `display_title`

The chapter H2 label is authored from chapter substance — a pure display-layer projection, one per chapter (not per lens):

```text
display_title = author( chapter substance )   # H2 under <!-- chapter:{cid} -->
  — presentation layer only; single SoT in _derive-{cid}.json; rendered at append-chapter
```

### 3.5 Document assembly

**Document assembly:** Compose documents use chapter anchors — `<!-- chapter:{cid} -->`, then `## {display_title}`, then body. Initializing persists each chapter via `$COMPOSE_DOC_CONTROL append-chapter`, which reads `_derive-{cid}.json` / `_body-{cid}.txt`. Downstream compose/eval tools locate chapters by chapter anchor, not H2 text. Section-key grammar retired (K3-d).

## Synthesis pipeline

> Cross-cutting (not a fourth layer): how the three layers combine on the Init path.

Sequential synthesis on the live Init path (fact-first chapters) — substance (§1) is dispatched through lenses (§2) and rendered per presentation (§3):

```text
chapter_body = Write( facts ; chapter_plan )  |  lenses / outline candidates
```

**Order (strict):** Atomize/validate facts (Step 2) → Derive (Step 3) → Organize chapters (Step 4) → Per-chapter write (Step 5: `_derive-{cid}.json` + `_body-{cid}.txt`) → `append-chapter` → Validate (Step 6).

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
