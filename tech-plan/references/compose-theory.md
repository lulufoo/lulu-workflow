# Compose Theory

> Referenced by: initializing-runner, refiner-runner (and any runner that generates section body content).

## Formula

Sequential synthesis (not independent factors):

```text
section_body = Write( I* ; F ; C )  |  desc
```

| Factor | Symbol | Source | Role |
|--------|--------|--------|------|
| Content | `I*` | desc + KW × decision | What to say (intent substance) |
| Form | `F` | domain + role + desc | How content is carried and organized |
| Expression | `C` | `### Role Fields` + domain + desc + F | How to write inside F |
| Envelope | `desc` | section-registry | Substance + form bounds throughout |

**Order (strict):** Filter `I*` → Derive `F` → Derive `C` → Write body.

## Form (F) — definition

F describes how a section's content is carried and organized. It has three fields:

- `carrier` — the primary container type for the content (the main vehicle through which information is presented)
- `structure` — the internal organization of the carrier: layout, hierarchy, diagram type and its communicative purpose
- `forbidden` — forms explicitly excluded for this section, derived from desc constraints and derivation conflicts

All three fields are derived natural-language descriptions, not enum values. F is derived per section; its value depends on domain conventions, role expressive tendency, and desc — in that priority order when they conflict.

## Expression (C) — definition

C is the set of writing constraints that govern how content is expressed inside F. It is a collection of `(d, c)` pairs where:

- `d` — the writing dimension (e.g., granularity, vocabulary, abstraction level, tone, completeness bar)
- `c` — the criterion for that dimension, derived from `### Role Fields`, domain instance, or `desc`

C has 2–5 pairs per section. Every `c` must be traceable to a specific `### Role Fields` field, `expression_conventions`, or `desc` clause; no pair is invented without grounding in these sources.

## Constraints

**Derivation:** Read `### Role Fields` and `domain instance` for F and C; infer per section dynamically. No static dimension tables, vocabulary enums, or form lookup configs.

**Prohibited:** decision-doc paste, `[Source: …]`, `decision-doc-mapping`, introducing intents not in decision-doc.
