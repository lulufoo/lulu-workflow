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
$REVISION_DIR/_title-display.json           # I2e (section_key → display title)
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
3. Display title → `（待补）`.

**Exception — derivation sections** (Partition path; see initializing-runner I2d Upstream derivation): rule 1 always applies (the gap entry notes the derivation source). **When derivation produces work items**, body and display title come from them and rules 2–3 do not apply. **When upstream bodies are also empty** (nothing to decompose), rules 2–3 apply unchanged (placeholder body + `（待补）` title) — never invent filler.

### Block title (`_title-block.json` entry)

1. One non-empty string value per `block_key`; localized reader-facing H2 for the whole outline block.
2. Must not verbatim-copy `blocks.{block_key}.heading` (English registry heading).
3. When block has no substance across intents → `（待补）`.
4. Must match the document `##` line above the block's first intent anchor after I2g.

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

`init_compose_validation.py validate` checks derive files, body files, `_title-display.json`, compose-doc anchors, and (when outline-registry is available) `_title-block.json` plus `section_order == flatten(outline.intents)`. When `drafting.inductive` is false, also requires a valid `$REVISION_DIR/_partition.json`. See script `--help` for exit codes and stderr format.
