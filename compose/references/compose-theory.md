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

## Formula

Sequential synthesis on the live Init path (fact-first chapters):

```text
chapter_body = Write( facts ; chapter_plan )  |  lenses / outline candidates

display_title = author( chapter substance )   # H2 under <!-- chapter:{cid} -->
  — presentation layer only; single SoT in _derive-{cid}.json; rendered at append-chapter
```

| Factor | Symbol | Source | Role |
|--------|--------|--------|------|
| Content | facts | `_facts.json` (K2 projects inductive `decisions[]`) | Filtered decision substance — what to say |
| Form | `F` | section guidance + domain + role + lens intent | How content is carried and organized (authoring lens) |
| Expression | `C` | Role Fields + domain + intent + F | How to write inside F |
| Envelope | lens / intent | section-registry (`intent` + `intent_boundary`) | what belongs vs belongs elsewhere |
| Section form | `presentation` / `expression` | section-form-registry | Carrier / expression constraints for authoring |
| Display title | `display_title` | `_derive-{cid}.json` at P2 | Chapter H2; projected by `append-chapter` |

**Order (strict):** Atomize/validate facts (P0) → Pd → Organize chapters (P1) → Per-chapter write (P2: `_derive-{cid}.json` + `_body-{cid}.txt`) → `append-chapter` → Validate (P3).

**Intent text:** Use `sections.{key}.intent` when present; else `sections.{key}.desc` (legacy).

### Inductive generation (`Induce`) — dual of `Write`

`Write` is deductive (known substance → organized prose). `Induce` is inductive (unknown substance → discover, ground, decide, fold): the inductive-runner produces per-section JSON SoT; K2 projects settled `decisions[].text` into `_facts.json` for Init P0 (not a legacy `$RESOLVE_I_STAR` read).

```text
section_json[S].decisions  ⊕=  Expand( open_point )   # via settle-open
open_point = Expose(trigger × means)  # kept iff ( frontier_KW row false  ∧  ¬Settled )
```

- `Expand` = ground (`attach-code-refs`) → AI leaning → **user decides** (auto/manual/ignore batch) ⇒ `settle-open` / `defer-open`.
- `⊕=` = append into that section's `decisions[]`; deepens by KW; never overwrites another section.
- Handoff: `decisions[].text` → `$INDUCTIVE_FACTS_PROJ project` → `_facts.json` → P0–P3.

`Expose` discovers open points via **trigger × means**. All sources subtract `¬Settled` (`decisions[]` only) and land in the owning section's `open[]`:

| trigger | means | probe | gap predicate | frontier_KW |
|---------|-------|-------|---------------|:---:|
| ai | `ai_scan` | run `methods` over code | KW row false | applies |
| ai | `intent_baseline` | demand manifest vs section | fulfillment false | applies |
| ai | `probe` | 4 black-box lenses (failure/boundary/assumption/seam) | silence ∧ KW-false | applies |
| human | `probe` / `direct` / `view` | user question / assertion / view-found gap | user assertion | exempt |

Seed is **not** an Expose source: it writes `decisions` with `trigger=seed` · `means=scope`. Design SSOT: `docs/biz/inductive-scope-section-sot-design.md` (+ `docs/biz/inductive-intent-baseline-source.md` for intent_baseline).

**F priority (conflict resolution):** section `presentation` > domain `expression_conventions` > role `expressive_tendency` > intent text. `intent_boundary` is an exclusion list — it names substance belonging to other intents; author none of it here.

**Document assembly:** Compose documents use chapter anchors — `<!-- chapter:{cid} -->`, then `## {display_title}`, then body. Initializing persists each chapter via `$COMPOSE_DOC_CONTROL append-chapter`, which reads `_derive-{cid}.json` / `_body-{cid}.txt`. Downstream compose/eval tools locate chapters by chapter anchor, not H2 text. Section-key grammar retired (K3-d).

## Init draft quality floor

Initializing must operationalize fact substance into readable chapters; scope-external speculation remains prohibited. `$INIT_COMPOSE_VALIDATE` gates Init completion via display-layer checks only. Contract: [`init-draft-quality.md`](init-draft-quality.md).

## Content (facts) — definition

**Facts** — filtered substance in `_facts.json`. Display-layer Init reads facts (K2 projects inductive `decisions[].text`). Scope doc is completeness cross-check only. Code grounding (when `drafting.code_grounding`) may add path/symbol detail at Write with `code_refs`.

- Covers goals, boundaries, exclusions, decisions, invariants, phases at the decision level.
- Rewrite as operational prose; not scope-doc verbatim paste (and not hand-rewriting inductive JSON beyond projection).
- Must not introduce capabilities, scope, or boundaries beyond inductive SoT / facts / grounded code.
- May leave a chapter as `（待补）` when coverage is intentionally open; do not invent filler.
- Must not restate propositions whose home chapter already carries them — cite by chapter reference instead.

**Codebase grounding (profile flag):** Driven by `drafting.code_grounding` (boolean; orthogonal to `drafting.inductive`). When `true`: at Write, bind named symbols in facts / registry-required path fields to real artifacts under `$PROJECT_ROOT` (Grep/Glob/Read, bounded); success → body increment + derive `code_refs` as `path` or `path#symbol`; failure → no invented paths, body `待决`. When `false`: Init does not run this pass — code refs come from inductive `attach-code-refs` upstream if at all. Grounding never writes back into inductive SoT.

## Form (F) — definition

F describes how a section's content is carried and organized. It has three fields:

- `carrier` — the primary container type for the content (the main vehicle through which information is presented)
- `structure` — the internal organization of the carrier: layout, hierarchy, diagram type and its communicative purpose
- `forbidden` — forms explicitly excluded for this section, derived from intent_boundary, section `guidance`, and derivation conflicts

All three fields are derived natural-language descriptions, not enum values. F is derived per section; its value depends on section `guidance`, domain conventions, role expressive tendency, and intent — in that priority order when they conflict.

## Expression (C) — definition

C is the set of writing constraints that govern how content is expressed inside F. It is a collection of `(d, c)` pairs where:

- `d` — the writing dimension (e.g., granularity, vocabulary, abstraction level, tone, completeness bar)
- `c` — the criterion for that dimension, derived from `### Role Fields`, domain instance, intent, section `presentation`, section `expression.required`/`expression.forbidden`, or `expression_conventions`

`expression_conventions` may include grounding clauses (e.g. cite paths only when verified elsewhere); they govern **how** to write, not **what** Init injects into `I*`.

C has 2–5 pairs per section. Every `c` must be traceable to a specific `### Role Fields` field, `expression_conventions`, section `presentation`, section `expression`, or intent clause; no pair is invented without grounding in these sources.

## Constraints

**Derivation:** Read `### Role Fields` and `domain instance` for F and C; infer per section dynamically. No static dimension tables, vocabulary enums, or form lookup configs.

**Prohibited:**

- scope-doc verbatim paste, `[Source: …]`, `decision-doc-mapping`
- facts / chapter prose that adds capabilities, scope, or boundaries not in scope / inductive SoT
- speculative paths, APIs, or behavior not grounded in scope / facts / inductive SoT / committed upstream decomposition, and not obtained via `drafting.code_grounding` (when enabled: ground or `待决` — never invent)
- `<!-- section-key:… -->` anchors or section-key Init artifact names (`_title-display.json`, `_partition.json`, `_derive-{section_key}.json`)
- verbatim `sections.{key}.heading` as chapter `display_title`