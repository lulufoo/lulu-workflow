# Init Draft Quality

> Referenced by: initializing-runner (I2 derive artifacts, I3 validate).  
> Theory: [`compose-theory.md`](compose-theory.md).

## Purpose

Per-section derive artifacts record I2a–I2c before body write. They make Init synthesis inspectable and gate-able without replacing Round probe.

## Init positioning

| Must | Must not |
|------|----------|
| Operationalize scope substance in readable `F` structure | Scope-external speculation |
| Mark scope gaps explicitly (`gaps` + body `待决`) | Decision verbatim paste |
| Produce non-shell sections (see empty `i_star` rules) | Empty shell bodies that pass only on non-empty text |

Round still owns formal KW / upstream / intent gap closure.

## Per-section artifacts

```text
$REVISION_DIR/_derive-{section_key}.json   # I2a–I2c (write before I2d)
$REVISION_DIR/_body-{section_key}.txt       # I2d
$REVISION_DIR/_title-display.json           # I2f projection of derive display_title (section_key → H3)
```

`section_key` is uppercase registry key (e.g. `GO`, `NS`).

## Per-block artifacts

```text
$REVISION_DIR/_title-block.json             # I2g (block_key → reader H2; last_in_block only)
```

`block_key` is uppercase outline block id (e.g. `SI`, `BD`). Written once when the last intent in that block completes I2f.

## `_derive-{key}.json` schema

| Field | Required | Rules |
|-------|----------|-------|
| `section_key` | yes | Must match filename key |
| `i_star` | yes | String; filtered substance for this section (tech-neutral). May be `""` |
| `display_title` | yes | Reader H3 authored at I2c (grounded in `i_star` + `C`); concise localized string, no code tokens, ≤ 40 chars; `（待补）` when empty `i_star` and no derivation |
| `scope_refs` | yes | Array of strings; scope anchors used (non-empty when any scope substance was considered). Derivation sections may include in-document upstream section anchors (e.g. `AR`, `SK-P1`) |
| `code_refs` | yes | Array of strings; codebase anchors as `path` or `path#symbol` (may be `[]`) |
| `gaps` | yes | Array of gap objects (may be empty when `i_star` non-empty) |
| `f.carrier` | yes | Non-empty string; selected from `presentation.allowed[].carrier` |
| `f.structure` | yes | String from `presentation.allowed[].structure` of the selected entry (`"none"` if no diagram) |
| `f.forbidden` | yes | String; derived from `presentation.forbidden` (may describe none) |
| `c` | yes | 2–5 objects, each `{ "d", "c", "source" }` — all non-empty strings |

**Removed:** `kw_init` (do not emit).

### Gap object

| Field | Required | Values |
|-------|----------|--------|
| `kind` | yes | `scope_absent` · `unfounded` |
| `note` | yes | Non-empty explanation |
| `dimension` | optional | `what` · `why` · `alternatives` · `failure` (KW-related absences) |

- `scope_absent` — scope/upstream lacks substance for this section (or a KW dimension).
- `unfounded` — body would need a claim with neither scope nor code provenance; mark gap + body `待决`, do not invent.

### Empty `i_star`

When no substance is assigned to this section:

1. `gaps` must contain at least one object explaining why.
2. Body may be a single honest placeholder, e.g. `（本节 scope 无可用 substance，待 Round 补）`.
3. `display_title` → `（待补）`.

**Exception — derivation sections** (Partition path; see initializing-runner I2d Upstream derivation): rule 1 always applies (the gap entry notes the derivation source). **When derivation produces work items**, body and display title come from them — I2c writes `display_title = （待补）` provisionally and I2d overwrites it from the derived work items; rules 2–3 do not apply. **When upstream bodies are also empty** (nothing to decompose), rules 2–3 apply unchanged (placeholder body + `（待补）` title) — never invent filler.

### Display title (`display_title` in derive → `_title-display.json` entry → H3)

`display_title` is authored in `_derive-{key}.json` at I2c (grounded in `i_star` + `C`); derivation sections finalize it at I2d from work items. At I2f, `append-intent` reads it from derive, renders the section H3, and — only after the section appends successfully — persists it to `_title-display.json` (a projection of derive). This is the only creative title decision; I2f is mechanical — there is no separate persist step.

1. A concise reader-facing H3 — a localized heading, optionally sharpened with one theme phrase (e.g. `现状与代价`). Keep it short.
2. Must not equal the registry `heading` for that section, or paste a full body / substance sentence.
3. Must not contain raw code tokens (file paths, API / symbol names, file extensions) — name *what* the section covers, not the implementation token.
4. Empty `i_star` with no derivation → `（待补）`.
5. Derive `display_title` is the single SoT: `_title-display.json[key]` and the document H3 must equal it after I2f.

Validator hard-gates (`init_compose_validation.py`), unless `（待补）`: non-empty · ≤ 40 chars · not equal to the registry heading · no code tokens. Plus the SoT equality in rule 5.

### Block title (`_title-block.json` entry)

1. `{n}. {neutral Chinese label from blocks.{block_key}.heading}` (`n` = 1-based outline order).
2. From outline `heading`.
3. Must not use English `heading` as the title, or body-derived H2 text.
4. Missing/empty outline heading → `（待补）`.
5. Must match the document `##` line above the block's first intent after I2g.

### Non-empty `i_star`

1. Body must be non-empty with at least three non-blank lines.
2. Body must reflect `f.carrier` structure (lists, tables, phased blocks as declared).
3. Scope gaps still require `gaps` entries and optional `> **待决：** …` in body — not invented fill.

### Partition (when `drafting.inductive` is false)

```text
$REVISION_DIR/_partition.json   # JSON array of {id, text, home}
```

I2a takes `i_star` from `$RESOLVE_I_STAR` (py keys off `drafting.inductive`). Do not re-scan the full scope for inclusive matching.

## Body prohibitions

- `[Source:` (decision paste marker)
- `decision-doc-mapping`

## Validate command

`init_compose_validation.py validate` checks derive files (including `display_title` hard-gates), body files, `_title-display.json`, compose-doc anchors, and (when outline-registry is available) `_title-block.json` plus `section_order == flatten(outline.intents)`. When `drafting.inductive` is false, also requires a valid `$REVISION_DIR/_partition.json`. See script `--help` for exit codes and stderr format.
