# Compose Theory

> Referenced by: initializing-runner, refiner-runner (and any runner that generates section body content).

## Formula

Sequential synthesis (not independent factors):

```text
section_body = Write( I* ; F ; C )  |  intent

display_title = specialize( sections.{key}.heading ; substance(content) )
  — presentation layer only; not part of body
```

| Factor | Symbol | Source | Role |
|--------|--------|--------|------|
| Content | `I*_scope` | intent + KW × decision | Scope, boundaries, decisions — what to say |
| Content | `I*_impl` | verified codebase read × desc | Paths, APIs, patterns — only when runner allows |
| Form | `F` | outline + domain + role + intent | How content is carried and organized |
| Expression | `C` | `### Role Fields` + domain + intent + F | How to write inside F |
| Envelope | `intent` | section-registry (`intent` + `intent_boundary`) | What belongs in this intent slice |
| Outline | `guidance` | outline-registry | Block-level form and presentation guidance for F derivation |
| Outline | `contract` | outline-registry | Structural required/forbidden constraints for C derivation |
| Display title | `display_title` | `sections.{key}.heading` + `I*_scope` / content substance | H3 label on intent anchor line under outline H2 blocks |

`I* = I*_scope ∪ I*_impl` (either list may be empty).

**Order (strict):** Filter `I*` → Derive `F` → Derive `C` → Write body → Derive display title → Persist section.

**Intent text:** Use `sections.{key}.intent` when present; else `sections.{key}.desc` (legacy).

**F priority (conflict resolution):** outline `guidance` > domain `expression_conventions` > role `expressive_tendency` > intent text. `intent_boundary` defers substance to other intents — do not repeat it in body.

**Document assembly:** Compose documents use outline-registry for structure — outline H2 blocks, intent H3 lines with `<!-- section-key:KEY -->`, then body. Initializing persists each intent via `$COMPOSE_DOC_CONTROL append-intent` immediately after display title derivation. Round readers locate sections by that anchor.

## Content (I*) — scope vs implementation

**I*_scope** — intent substance traceable to decision-doc:

- Filtered by `intent` (or `desc`) and section KW criteria.
- Covers goals, boundaries, exclusions, decisions, invariants, phases at the decision level.
- Must not introduce capabilities or scope beyond decision-doc.

**I*_impl** — implementation substance traceable to decision **and** verified codebase read:

- Allowed only when the active runner's contract permits codebase read for the section.
- Covers concrete file paths, module names, public APIs, DOM ids, reference patterns (e.g. an existing dialog to mirror).
- Must be supported by files or symbols actually read — no invented paths.
- Must not introduce capabilities beyond decision-doc scope.

## Form (F) — definition

F describes how a section's content is carried and organized. It has three fields:

- `carrier` — the primary container type for the content (the main vehicle through which information is presented)
- `structure` — the internal organization of the carrier: layout, hierarchy, diagram type and its communicative purpose
- `forbidden` — forms explicitly excluded for this section, derived from intent_boundary, outline `guidance`, and derivation conflicts

All three fields are derived natural-language descriptions, not enum values. F is derived per section; its value depends on outline `guidance`, domain conventions, role expressive tendency, and intent — in that priority order when they conflict.

## Expression (C) — definition

C is the set of writing constraints that govern how content is expressed inside F. It is a collection of `(d, c)` pairs where:

- `d` — the writing dimension (e.g., granularity, vocabulary, abstraction level, tone, completeness bar)
- `c` — the criterion for that dimension, derived from `### Role Fields`, domain instance, intent, outline `guidance`, outline `contract.required`/`contract.forbidden`, or `expression_conventions` (including codebase-grounding clauses)

C has 2–5 pairs per section. Every `c` must be traceable to a specific `### Role Fields` field, `expression_conventions`, outline `guidance`, outline `contract`, or intent clause; no pair is invented without grounding in these sources.

## Constraints

**Derivation:** Read `### Role Fields` and `domain instance` for F and C; infer per section dynamically. No static dimension tables, vocabulary enums, or form lookup configs.

**Prohibited:**

- decision-doc verbatim paste, `[Source: …]`, `decision-doc-mapping`
- `I*_scope` that adds capabilities, scope, or boundaries not in decision-doc
- `I*_impl` without verified codebase read, or that adds capabilities beyond decision-doc
- speculative paths, APIs, or behavior not grounded in decision or read code
- verbatim `sections.{key}.heading` as document display title (infer via `display_title` instead)
