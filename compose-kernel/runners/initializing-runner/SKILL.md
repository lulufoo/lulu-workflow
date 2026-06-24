---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads upstream scope
  doc and frameworks; composes per-section body via I* / F / C derive artifacts;
  validates draft quality; persists each section incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** I1 Load → I2 Compose (per section) → I3 Validate → Return.

Init writes a readable draft from scope substance only.

- **Must:** operationalize scope content; explicit 待决 for scope gaps; readable `F` structure.
- **Must not:** scope-external speculation; decision paste; empty shell sections.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../../references/compose-theory.md`](../../references/compose-theory.md).

Derive artifact contract: [`../../references/init-draft-quality.md`](../../references/init-draft-quality.md).

**Order (strict):** I2a Filter `I*` → I2b Derive `F` → I2c Derive `C` → I2d Write body → I2e Derive display title → I2f Persist section.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_DOC_PATH` | Absolute path to compose intent SSOT (design-doc or decision-doc) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`)

All compose and scope macros **must** pass `--profile "$COMPOSE_PROFILE"`. `$FETCH_COMPOSE` **must** also pass `--cycle-id "$CYCLE_ID"`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-domain --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/compose_doc_control.py"` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/init_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-intent` (use `--body-file` + `--display-title-file` in I2f).

## Execution Contract

### Step I1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE section-registry --cycle-id "$CYCLE_ID"` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `intent` (else `desc`) / `intent_boundary`
   `$FETCH_COMPOSE section-form-registry --cycle-id "$CYCLE_ID"` → `sections.{key}.guidance` / `contract`
4. `$FETCH_COMPOSE outline-registry --cycle-id "$CYCLE_ID"` → `outline_order`, per-block `heading` / `intents`.
5. `$FETCH_COMPOSE section-kw-criteria --cycle-id "$CYCLE_ID"` → each `## {section_key}` block.
6. Read `$SCOPE_DOC_PATH` full text once (shared across I2).
7. **Init document:** Substitute placeholders in `document_preamble`. Write via:

```bash
$COMPOSE_DOC_CONTROL init-doc \
  --path "$OUTPUT_DOC_PATH" \
  --preamble "<substituted document_preamble markdown>"
```

Prefer `--preamble-file` when content is multiline.

Do **not** append outline-registry content to the deliverable header. Do **not** fetch spec-template URLs.

**Done:** `$OUTPUT_DOC_PATH` exists with preamble only.

### Step I2 — Compose (per `section_key`, strict I2a → I2f)

For each key in `section_order`, produce three artifacts under `$REVISION_DIR`:

```text
_derive-{section_key}.json   # I2a–I2c (must exist before I2d)
_body-{section_key}.txt      # I2d
_title-{section_key}.txt     # I2e
```

Field schema: [`init-draft-quality.md`](../../references/init-draft-quality.md).

#### I2a — Filter `I*`

- **Input:** scope doc · `sections.{key}.intent` (else `desc`) · `intent_boundary` · kw `## {key}`
- **Action:** Include scope substance matching `intent` and at least one KW dimension (semantic; do not label KW numbers). Exclude content belonging to other sections. **Must-effort:** extract all matching scope substance; use `gaps` for scope absences — do not silently omit.
- **Output:** write `i_star`, `scope_refs`, `gaps`, `kw_init` into `_derive-{key}.json`
- **Done:** derive file exists with `i_star` / `scope_refs` / `gaps` populated per contract

#### I2b — Derive `F`

- **Input:** `### Role Fields` · domain instance · `intent` · `sections.{key}.guidance`
- **Action:** Three-step narrowing (section guidance > domain > role > intent). See compose-theory · Form (F).
- **Output:** write `f.carrier`, `f.structure`, `f.forbidden` into `_derive-{key}.json`
- **Done:** `f.carrier` non-empty in derive file

#### I2c — Derive `C`

- **Input:** `### Role Fields` · domain instance · `intent` · `sections.{key}.contract` · `F`
- **Action:** Derive 2–5 `(d, c, source)` pairs traceable to Role, intent, contract, or `expression_conventions`. Finalize `kw_init` booleans with matching `gaps` for false dimensions when scope lacks substance.
- **Output:** write `c` and finalized `kw_init` into `_derive-{key}.json`
- **Done:** derive file complete; **do not start I2d until derive validates mentally against init-draft-quality**

#### I2d — Write body

- **Input:** `_derive-{key}.json` · `intent` · `intent_boundary` · upstream bodies in `$OUTPUT_DOC_PATH` (de-duplication)
- **Action:** Scaffold per `F`; rewrite `I*` into slots; obey every `C` pair and `intent`. Mark scope gaps with `> **待决：** …` when `gaps` present.
- **De-duplication:** Do not repeat boundary constraints deferred by `intent_boundary`. Read upstream via `compose_doc_schema.py --section-body` when needed.
- **Output:** `$REVISION_DIR/_body-{section_key}.txt` (no H2 line)
- **Done:** body file exists; non-empty; ≥3 non-blank lines when `i_star` non-empty

#### I2e — Derive display title

- **Input:** `sections.{key}.heading` · body file · `i_star` substance
- **Action:** Short localized title (~8–20 chars): type anchor from `heading` + one domain theme from substance.
- **Forbidden:** verbatim registry `heading`; file paths; API names; copying first body sentence
- **Output:** `$REVISION_DIR/_title-{section_key}.txt`; empty `i_star` → `（待补）`
- **Done:** title file exists with one non-empty line

#### I2f — Persist section

```bash
$COMPOSE_DOC_CONTROL append-intent \
  --path "$OUTPUT_DOC_PATH" \
  --section "{section_key}" \
  --display-title-file "$REVISION_DIR/_title-{section_key}.txt" \
  --body-file "$REVISION_DIR/_body-{section_key}.txt" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

- **Done:** `$OUTPUT_DOC_PATH` contains `<!-- section-key:{key} -->` for this section

All sections remain draft until Round probe.

### Step I3 — Validate

1. Run `$INIT_COMPOSE_VALIDATE`.
2. On failure → read stderr; fix cited sections (return to I2 for those keys); re-run I3.
3. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Initializing complete.
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Derive artifacts: <REVISION_DIR>/_derive-*.json
  Synthesized sections: <space-separated section keys from section_order>
  Scope SSOT: <SCOPE_DOC_PATH>
  Draft status: pending Round validation (all sections X until probe)
  Next step: RoundIteration, or parent pause gate (user may skip Round and Evaluate/Deliver)
```
