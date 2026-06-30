# Compose Theory

> Referenced by: initializing-runner (and any runner that generates section body content).

## Profile SSOT

Compose stage configuration lives at `{WORKFLOW_ROOT}/{stage}/compose-profile.json` (not under `compose-kernel/profiles/`). After `start`, runtime resolves the same file via session cache pointer `.compose-profile-path` under `{cache_subdir}/`.

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

Sequential synthesis (not independent factors):

```text
section_body = Write( I* ; F ; C )  |  intent

display_title = specialize( sections.{key}.heading ; substance($SECTION_BODY) )
  — presentation layer only; not part of body

block_title = specialize( blocks.{id}.heading ; substance(block intent bodies) )
  — H2 presentation layer; derived at last_in_block, patched after all intents in block persist
```

| Factor | Symbol | Source | Role |
|--------|--------|--------|------|
| Content | `I*` | scope doc × intent + KW | Filtered decision substance for this section — what to say |
| Form | `F` | section guidance + domain + role + intent | How content is carried and organized |
| Expression | `C` | `### Role Fields` + domain + intent + F | How to write inside F |
| Envelope | `intent` | section-registry (`intent` + `intent_boundary`) | What belongs in this intent slice |
| Section form | `presentation` | section-form-registry | Per-intent carrier selection guidance, allowed carriers, and forbidden carriers for F derivation |
| Section form | `expression` | section-form-registry | Per-intent required/forbidden expression constraints for C derivation |
| Display title | `display_title` | `sections.{key}.heading` + content substance | H3 label on intent anchor line under outline H2 blocks |
| Block title | `block_title` | `blocks.{id}.heading` + block intent substance | H2 reader label; placeholder = registry heading until I2g |

**Order (strict):** Filter `I*` → Derive `F` → Derive `C` → Write body → Derive display title → Persist section → [when last intent in block] I2g Block close (derive block title → patch H2).

**Intent text:** Use `sections.{key}.intent` when present; else `sections.{key}.desc` (legacy).

**F priority (conflict resolution):** section `presentation` > domain `expression_conventions` > role `expressive_tendency` > intent text. `intent_boundary` defers substance to other intents — do not repeat it in body.

**Document assembly:** Compose documents use outline-registry for structure — outline H2 blocks, intent H3 lines with `<!-- section-key:KEY -->`, then body. Initializing persists each intent via `$COMPOSE_DOC_CONTROL append-intent` immediately after display title derivation; when the last intent in a block is persisted, `$COMPOSE_DOC_CONTROL patch-block-heading` replaces the English H2 placeholder with the inferred block title. Downstream compose tools locate sections by section-key anchor, not H2 text.

## Init draft quality floor

Initializing must operationalize scope substance in readable form; scope-external speculation remains prohibited. Per-section `_derive-{key}.json` records I2a–I2c before body write; `$INIT_COMPOSE_VALIDATE` gates Init completion. **Best-effort applies to scope-external speculation only** — not to scope-internal completeness or readable `F` structure. Contract: [`init-draft-quality.md`](init-draft-quality.md).

## Content (I*) — definition

**I*** — filtered substance grounded in the scope doc (`$SCOPE_DOC_PATH`), best-effort supplemented by available codebase facts

- Produced in I2a: match `intent` (else `desc`), `intent_boundary`, and section KW criteria (`## {key}`).
- Covers goals, boundaries, exclusions, decisions, invariants, phases at the decision level.
- Rewrite as operational prose; not scope-doc verbatim paste.
- Must not introduce capabilities, scope, or boundaries beyond the scope doc.
- May be empty when no matching substance exists.

**Codebase grounding (best-effort default):** Initializing attempts to bind scope-doc semantic names to identifiable system artifacts. No match → no-op, not an error. Names still unresolvable after the attempt must be flagged in OQ as blocks-plan.

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
- `I*` that adds capabilities, scope, or boundaries not in scope doc
- speculative paths, APIs, or behavior not grounded in scope doc (Init does not invent implementation detail)
- verbatim `sections.{key}.heading` as document display title (infer via `display_title` instead)
- verbatim `blocks.{id}.heading` as final block H2 (infer via `block_title` in I2g instead)
