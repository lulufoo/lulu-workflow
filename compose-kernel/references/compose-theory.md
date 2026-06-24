# Compose Theory

> Referenced by: initializing-runner, refiner-runner (and any runner that generates section body content).

## Profile SSOT

Compose stage configuration lives at `{WORKFLOW_ROOT}/{stage}/compose-profile.json` (not under `compose-kernel/profiles/`). After `start`, runtime resolves the same file via session cache pointer `.compose-profile-path` under `{cache_subdir}/`.

## Formula

Sequential synthesis (not independent factors):

```text
section_body = Write( I* ; F ; C )  |  intent

display_title = specialize( sections.{key}.heading ; substance($SECTION_BODY) )
  — presentation layer only; not part of body
```

| Factor | Symbol | Source | Role |
|--------|--------|--------|------|
| Content | `I*` | scope doc × intent + KW | Filtered decision substance for this section — what to say |
| Form | `F` | section guidance + domain + role + intent | How content is carried and organized |
| Expression | `C` | `### Role Fields` + domain + intent + F | How to write inside F |
| Envelope | `intent` | section-registry (`intent` + `intent_boundary`) | What belongs in this intent slice |
| Section form | `guidance` | section-registry | Per-intent form guidance for F derivation |
| Section form | `contract` | section-registry | Per-intent required/forbidden constraints for C derivation |
| Display title | `display_title` | `sections.{key}.heading` + content substance | H3 label on intent anchor line under outline H2 blocks |

**Order (strict):** Filter `I*` → Derive `F` → Derive `C` → Write body → Derive display title → Persist section.

**Intent text:** Use `sections.{key}.intent` when present; else `sections.{key}.desc` (legacy).

**F priority (conflict resolution):** section `guidance` > domain `expression_conventions` > role `expressive_tendency` > intent text. `intent_boundary` defers substance to other intents — do not repeat it in body.

**Document assembly:** Compose documents use outline-registry for structure — outline H2 blocks, intent H3 lines with `<!-- section-key:KEY -->`, then body. Initializing persists each intent via `$COMPOSE_DOC_CONTROL append-intent` immediately after display title derivation. Round readers locate sections by that anchor.

## Content (I*) — definition

**I*** — filtered substance grounded in the scope doc (`$SCOPE_DOC_PATH`), supplemented by codebase facts when section intent requires existing-system grounding

- Produced in I2a: match `intent` (else `desc`), `intent_boundary`, and section KW criteria (`## {key}`).
- Covers goals, boundaries, exclusions, decisions, invariants, phases at the decision level.
- Rewrite as operational prose; not scope-doc verbatim paste.
- Must not introduce capabilities, scope, or boundaries beyond the scope doc.
- May be empty when no matching substance exists.

When section intent requires existing-system grounding, Initializing reads relevant codebase surfaces to complete `I*`. Speculative detail not anchored to the scope doc's impact surface belongs to Round refiner, FreeEdit, or Eval.

## Form (F) — definition

F describes how a section's content is carried and organized. It has three fields:

- `carrier` — the primary container type for the content (the main vehicle through which information is presented)
- `structure` — the internal organization of the carrier: layout, hierarchy, diagram type and its communicative purpose
- `forbidden` — forms explicitly excluded for this section, derived from intent_boundary, section `guidance`, and derivation conflicts

All three fields are derived natural-language descriptions, not enum values. F is derived per section; its value depends on section `guidance`, domain conventions, role expressive tendency, and intent — in that priority order when they conflict.

## Expression (C) — definition

C is the set of writing constraints that govern how content is expressed inside F. It is a collection of `(d, c)` pairs where:

- `d` — the writing dimension (e.g., granularity, vocabulary, abstraction level, tone, completeness bar)
- `c` — the criterion for that dimension, derived from `### Role Fields`, domain instance, intent, section `guidance`, section `contract.required`/`contract.forbidden`, or `expression_conventions`

`expression_conventions` may include grounding clauses (e.g. cite paths only when verified elsewhere); they govern **how** to write, not **what** Init injects into `I*`.

C has 2–5 pairs per section. Every `c` must be traceable to a specific `### Role Fields` field, `expression_conventions`, section `guidance`, section `contract`, or intent clause; no pair is invented without grounding in these sources.

## Constraints

**Derivation:** Read `### Role Fields` and `domain instance` for F and C; infer per section dynamically. No static dimension tables, vocabulary enums, or form lookup configs.

**Prohibited:**

- scope-doc verbatim paste, `[Source: …]`, `decision-doc-mapping`
- `I*` that adds capabilities, scope, or boundaries not in scope doc
- speculative paths, APIs, or behavior not grounded in scope doc (Init does not invent implementation detail)
- verbatim `sections.{key}.heading` as document display title (infer via `display_title` instead)
