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
$REVISION_DIR/_title-{section_key}.txt      # I2e
```

`section_key` is uppercase registry key (e.g. `GO`, `NS`).

## `_derive-{key}.json` schema

| Field | Required | Rules |
|-------|----------|-------|
| `section_key` | yes | Must match filename key |
| `i_star` | yes | String; filtered scope substance (tech-neutral). May be `""` |
| `scope_refs` | yes | Array of strings; decision headings or paraphrase anchors used |
| `gaps` | yes | Array of gap objects (may be empty when `i_star` non-empty) |
| `f.carrier` | yes | Non-empty string |
| `f.structure` | yes | String (`"none"` if no diagram) |
| `f.forbidden` | yes | String (may describe none) |
| `c` | yes | 2–5 objects, each `{ "d", "c", "source" }` — all non-empty strings |
| `kw_init` | yes | `{ "what", "why", "alternatives", "failure" }` booleans |

### Gap object

| Field | Required | Values |
|-------|----------|--------|
| `kind` | yes | `scope_absent` |
| `note` | yes | Non-empty explanation |
| `dimension` | when KW-related | `what` · `why` · `alternatives` · `failure` |

When scope lacks substance for a KW dimension: set `kw_init.<dim>` to `false` and add a `scope_absent` gap with matching `dimension`.

### Empty `i_star`

When no scope substance matches this section:

1. `gaps` must contain at least one object explaining why.
2. Body may be a single honest placeholder, e.g. `（本节 scope 无可用 substance，待 Round 补）`.
3. Display title → `（待补）`.

### Non-empty `i_star`

1. Body must be non-empty with at least three non-blank lines.
2. Body must reflect `f.carrier` structure (lists, tables, phased blocks as declared).
3. Scope gaps still require `gaps` entries and optional `> **待决：** …` in body — not invented fill.

## Body prohibitions

- `[Source:` (decision paste marker)
- `decision-doc-mapping`

## Validate command

`init_compose_validation.py validate` checks derive files, body/title files, and compose-doc anchors. See script `--help` for exit codes and stderr format.
